# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

A **hackathon working directory** for the NormaCore "AI-Powered Robot Control" track (Berlin AI x Robotics), not a library. It drives **NormaCore's 8-DOF ElRobot arm** (joints `j1`–`j8`) over NormaCore's `normfs` bus. Two things work here today:

1. **A reliable manual pick** — Claude picks a carrot off a white sheet using a taught-grid IK + overload-safe incremental motion, with **no policy**. This is the hero/fallback demo and it is proven on hardware. See `smooth_pick.py`.
2. **A trained SmolVLA policy** (`smolvla_ckpt/final`, loss ~0.045) plus the supervisor scaffolding for the "two-brain" demo (fast VLA + slow Claude supervisor). The VLA story needs a stable camera to test; the manual pick does not.

The original vision ("The Supervisor": Claude overseeing a SmolVLA, preempting it on failure) is in [PLAN.md](PLAN.md) / [SUPERVISOR.md](SUPERVISOR.md). The day-to-day reality is the manual pick.

## The control stack

Three processes over `normfs` (protobuf/TCP), two control rates:

1. **`station` binary** — NormaCore's hardware platform. Owns the ST3215 servo bus + USB cameras, serves **normfs (`:8888`)** and a read-only **web UI (`:8889`)**. Config in [station.yaml](station.yaml). **Must be started with `-t`** or `:8888` is not served.
2. **Fast brain — SmolVLA runner** (`norma-core/software/ai/smolvla_py/scripts/run_policy_supervised.py`, our patched copy that re-reads `vla_goal.txt` + `vla_pause` each loop so it can be preempted). ~10 Hz on the GPU.
3. **Slow brain — the Supervisor** (a Claude Code session, ~0.3 Hz) talking to the **`station_mcp.py`** MCP server (FastMCP, wraps `robot_lib`).

## The control layer: `robot_lib.py`

Everything goes through [robot_lib.py](robot_lib.py) — it wraps the cloned `norma-core` station client + generated protobufs. Key calls:

- `connect("localhost")` → normfs client.
- `observe(cli)` → one normvla frame = **camera JPEGs + joint state together**. Reads `inference/normvla`. **This FREEZES when the camera feed drops** (see gotchas) — do not rely on it for motion control.
- **`current_st3215(cli)`** → live joint norms + per-joint ranges read straight from the **motor bus** (`st3215/inference`). **Camera-independent — never freezes.** This is the read used by all motion control. Returns `({jname: norm}, [(rmin,rmax), ...])`.
- `move_norm(cli, bus, motor_ids, goals_norm, ranges)` → one **atomic sync-write** of all joints, normalized `[0,1]` per joint → calibrated raw ticks.
- `discover_bus_serial` / `list_buses` → find the follower bus (there are two buses; leader + follower).

Control is always **normalized `[0,1]`** per joint, mapped through each joint's calibrated `(range_min, range_max)`.

## normfs protocol (verified on hardware)

- **Move a joint:** `ST3215SyncWriteCommand{address: 0x2A, motors:[{motor_id, value: int.to_bytes(2,"little")}]}` wrapped in `DriverCommand{STC_ST3215_COMMAND}` → `send_commands(cli, [cmd])`. **Write target register = `0x2A`.**
- **Read joints:** `st3215/inference` → `InferenceStateReader` → per-bus motors; **present-position register = `0x38`**, sign-normalized (`_norm_raw` in robot_lib). 8 motors, ordered by motor id 1..8 = `j1`..`j8`.
- **Read camera:** `usb-video` (FramesPack, JPEG, 224px) or via `observe()`'s normvla frame (`get_images()` → `get_jpeg()`, cam0 + cam1 in one frame).
- **Bus serial:** follower = **`5B61034836`** (leader = `5B61034574` — **never command the leader**).

## Hardware facts (learned the hard way — do not re-derive)

- **8-DOF**, not 6. Motors `j1`–`j8`.
- **Gripper jaws = `j8`** (open ≈ 0.78, close until it stalls ≈ 0.22–0.34 = a real grip). **`j7` = gripper ROTATION** (≈ 0.45 at grasp), NOT the jaws. *(Note: `.mcp.json` still sets `ROBOT_GRIPPER_JOINT=j7` — that is the rotation joint; `set_gripper` should target `j8` to open/close. Fix when next touching the MCP server.)*
- **`j2` (shoulder) OVERLOADS** if commanded directly to a reaching pose (gravity torque → ST3215 faults the motor, status reg `0x41` = `0x20`). Avoid by: **creeping in small steps with pauses**, and **tucking the elbow `j3` in before raising the shoulder** so the load sits near the base. Never raise `j2` while the arm is extended. `station.yaml` `current-threshold` is already raised to 200.
- **Lift recipe:** after gripping — (1) retract `j3` + pitch `j4` up (tuck), (2) *then* lower `j2` toward home (arm folds up) to clear the ground, (3) *then* traverse home. Encoded in `smooth_pick.py grip`.
- Two workspace cameras: Logitech C270 (`046d:0825`) + generic (`1e45:0209`) = cam0/cam1. **Camera order flips on replug** — identify by content (jaws visible in frame = wrist cam), not by index.

## The manual-pick pipeline (the working demo)

- **[grid_grasp.json](grid_grasp.json)** — a taught 3×3 grid (`TL`..`BR`) of grasp poses over the sheet, each label → `(u,v)` + full `j1..j8` pose. Recorded via teleop.
- **[grasp_model.py](grasp_model.py)** — `grasp_pose(u, v)`: bilinear interpolation over the grid → a grasp pose for any sheet position `(u: left0..right1, v: top0..bottom1)`.
- **[smooth_pick.py](smooth_pick.py)** — the overload-safe executor, **driven entirely off `current_st3215` (camera-independent)**. `goto()` creeps each joint in `STEP` (0.03) increments with `DT` (0.5s) pauses and auto-relieves shoulder stalls by retracting `j3`. Commands: `home`, `approach <u> <v>`, `grip` (close → 2-stage lift → carry home holding the carrot). **Runs as one autonomous script so Claude is not in the per-step loop.**
- **[grasp_offsets.md](grasp_offsets.md)** — systematic offset the user observed: correction order is gripper-rotate → left → forward. **Direction is flipped vs the user's view: user's-LEFT = INCREASE `u`.**
- **[teach_points.py](teach_points.py)** (grid teach, camera-based) and **[teach_drop.py](teach_drop.py)** (drop-path teach, motor-bus / freeze-proof) — interactive teleop recorders; the user moves the arm, the script snapshots poses.
- [pick_recipe.json](pick_recipe.json) — the gripper/lift constants in one place. [locate_carrot.py](locate_carrot.py) — opencv localizer (unreliable; confuses orange servo horns for the carrot — prefer manual `(u,v)`).

## Commands

Start the station (arm + cameras attached; on the robot host):
```bash
sudo ./fix_camera_perms.sh                    # station opens cameras via libusb — needs /dev/bus/usb rw
./station --config station.yaml -t --web      # normfs :8888 (the -t is REQUIRED), web UI :8889
```

Run the manual pick (camera-independent, overload-safe):
```bash
.venv/bin/python smooth_pick.py approach <u> <v>   # home -> creep to grasp pose, jaws open
# verify wrist-cam alignment (carrot centered between jaws), then:
.venv/bin/python smooth_pick.py grip               # close -> lift -> carry home holding carrot
.venv/bin/python smooth_pick.py home               # open jaws, return home (release)
```

When the camera is frozen, the MCP `observe` shows a **stale** frame — read the true state from the motor bus instead (`robot_lib.current_st3215`).

Launch the Supervisor (a Claude Code session as the slow brain) — **append**, never `--system-prompt-file` (that strips Claude Code's tooling):
```bash
claude --dangerously-skip-permissions --append-system-prompt "$(cat SUPERVISOR.md)"
```
Safe with `--dangerously-skip-permissions` only because the safety envelope (joint/step clamps) lives inside the MCP server / `move_norm`.

Run the VLA / hero two-brain demo, then resume training:
```bash
./run_hero_demo.sh        # frees GPU, starts newest smolvla_ckpt/* policy; arm will move — watch it
./resume_training.sh      # resume fine-tuning afterward (watchdog.sh auto-restarts on stall)
```

## Conventions for working here

- Motor commands are **absolute, bounded targets**, never relative nudges (re-issuing a target is idempotent/self-correcting).
- **The MCP server / `move_norm`, not the model, enforces safety** (clamp `[0,1]`, max step per call). Read tools `readOnlyHint`, motion tools `destructiveHint`.
- **Drive motion off `current_st3215`, not `observe`** — the camera feed freezes and would stall a move mid-way on a stale read.
- **Bundle whole motions into one script call** (like `smooth_pick.py`) so Claude is a once-per-task overseer, not a per-step bottleneck (each Claude step costs observe + reasoning latency).
- Always keep the **manual pick working** as a fallback demo, independent of whether the VLA cooperates.
- The MCP server is spawned once per Claude session and **can't hot-reload** — after editing `station_mcp.py` / `.mcp.json`, the user must start a fresh `claude` session.

## Gotchas (all solved, scripted)

- Station unreachable on `:8888` → missing `-t` flag.
- Camera "not capturing" / normvla frozen → station opens cameras via **libusb**, needs `/dev/bus/usb/*` rw (not just `/dev/video*`) → `sudo ./fix_camera_perms.sh` (+ `install_camera_udev.sh` for persistence). Cameras also brown out / re-enumerate under USB load → a powered hub is the real fix.
- Servos default to MAX speed after calibration → `slow_servos.py` before motion.
- `train.py` hardcoded dim 6 vs 8-DOF data → fixed to derive dims from the dataset.
- Checkpoint numbers reset each training resume → use **newest-by-mtime**, not highest number (`run_hero_demo.sh` already does `ls -dt`).

## Do NOT touch

[CLAUDE-FABLE-5.md](CLAUDE-FABLE-5.md) is a copy of the claude.ai consumer system prompt — **not** robot guidance. Never feed it to the robot agent (it strips Claude Code's tooling). Use [SUPERVISOR.md](SUPERVISOR.md) via `--append-system-prompt` instead.
