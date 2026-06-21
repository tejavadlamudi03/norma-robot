# The Supervisor — Hackathon Plan

**Track:** AI-Powered Robot Control (NormaCore / ElRobot) · **Judge:** Paul · **Budget:** ~30h · **Prize:** 1 ElRobot

## One-liner

> **An LLM (Claude Code) that supervises a real-time VLA controlling the ElRobot — it watches the camera every cycle, sets the policy's language goal, and *preempts the policy to hand-correct with direct joint commands* the moment the VLA gets stuck.**

This hits the track's exact ask (an LLM controlling the robot by looking through cameras) and goes one layer deeper than any pure "LLM-moves-arm" demo by riding on NormaCore's own `inference/normvla` bridge.

---

## Architecture — two brains, two clocks

```
  ┌─────────────────────────────────────────────────────────────┐
  │  SLOW BRAIN  ·  Claude Code (Opus/Fable, vision)  ·  ~0.3 Hz  │
  │  - observe(): gets camera frame + joint state via MCP        │
  │  - decides: on-track? stuck? unsafe?                          │
  │  - acts: set_vla_goal / pause_vla / move_joints / resume_vla  │
  └──────────────┬───────────────────────────────▲───────────────┘
                 │ MCP (stdio)                    │ image + state
                 ▼                                │
  ┌─────────────────────────────────────────────────────────────┐
  │  station_mcp.py  — MCP server wrapping the station API        │
  │  - reads usb-video + st3215/inference (normfs :8888)          │
  │  - writes ST3215 DriverCommands                               │
  │  - writes goal to vla_goal.txt / pause flag                   │
  └──────────────┬───────────────────────────────▲───────────────┘
                 │ normfs (protobuf/TCP :8888)    │
                 ▼                                │
  ┌─────────────────────────────────────────────────────────────┐
  │  FAST BRAIN  ·  patched run_policy.py (SmolVLA, GPU)  · 10 Hz  │
  │  - reads inference/normvla obs, runs SmolVLA, writes actions  │
  │  - PATCH: re-reads goal + pause flag every loop               │
  └──────────────┬──────────────────────────────────────────────┘
                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  station binary  ·  ST3215 servos (6-DOF) + USB camera        │
  └─────────────────────────────────────────────────────────────┘
```

**Why this wins:** the supervisor is *useful precisely because* SmolVLA is imperfect zero-shot. Claude catches the failure the VLA can't see itself in, and corrects. That's a real capability, demoable live, and a clean research story (runtime monitoring + preempt-and-correct, not plan-time decomposition).

---

## Novelty pitch (what to tell Paul)

Prior LLM-for-manipulation work puts the LLM **upstream at plan time**: SayCan scores skills, Code-as-Policies emits programs, VoxPoser builds value maps; RT-H / Hi Robot add a high-level *VLM* that decomposes instructions into atomic commands for a low-level VLA. **Ours is a runtime *supervisor*:** a general foundation-model agent watching raw camera frames each cycle, detecting stuck/failure states, and **preempting an already-autonomous reactive VLA to inject corrective joint commands** — automating the human-correction idea RT-H only did with a human in the loop. Two things are genuinely new in combination: (1) the loop closes on **camera frames returned through MCP image tool-results** using an off-the-shelf agent runtime (Claude Code) — a deployable, model-agnostic pattern, no trained high-level policy; (2) a **preempt-and-correct authority channel** (pause → joint command → resume). *Be honest:* hierarchical LLM+VLA and LLM-as-controller are established — our defensible claim is the **runtime failure-detection + autonomous preemption** layer and the **MCP deployment pattern.**

---

## 30-hour milestone plan (with fallback tiers)

| # | Hours | Milestone | "Done" = demoable |
|---|---|---|---|
| **0** | 0–2 | **Env + ground truth.** Clone `norma-core`, generate Python protobufs, confirm queue names (`usb-video`, `st3215/inference`, `st3215/tx`) against the running station. Find the bus serial in the web UI (:8889). | `station_probe.py` prints a live joint vector + saves a camera JPEG. |
| **1** | 2–6 | **MCP server v1 (read path).** `observe()` returns frame image + joint state to Claude Code. Register via `.mcp.json`. | In a Claude Code session, ask "what do you see?" and it describes the real camera. |
| **2** | 6–10 | **MCP server v2 (write path).** `move_joints()`, `set_gripper()`, `get_joint_state()` with a **safety envelope** (joint limits, max velocity, workspace clamp, rate limit). | Claude Code moves the arm to a pose you describe in words, safely. **← TIER-1 demo already exists here.** |
| **3** | 10–16 | **Fast brain online.** Get `smolvla_py/run_policy.py` running with `lerobot/smolvla_base`; patch it to re-read `vla_goal.txt` + `vla_pause` every loop. | VLA drives the arm toward a typed goal; you can change/pause the goal live. |
| **4** | 16–22 | **The Supervisor loop.** `set_vla_goal / pause_vla / resume_vla` tools + the `CLAUDE-FABLE-5.md` system prompt. Claude runs perceive→reason→act→re-perceive. | Claude sets a goal, watches, detects "VLA stuck," pauses, nudges, resumes. **← TIER-2 hero demo.** |
| **5** | 22–24 | **(Optional) Fine-tune.** If SmolVLA base is too weak, record ~30 episodes with `dataset-generator` and fine-tune (`scripts/train.py`) on a HF/cloud GPU. | VLA succeeds more often, so corrections are rarer + cleaner. |
| **6** | 24–30 | **Polish + demo script + recording.** Narration overlay, failure-injection moment, backup video. | Reliable 2-minute live run + a recorded fallback. |

**Fallback ladder (always have a working demo):**
- **T0 (safety net):** Claude Code directly teleoperates the arm by voice/text via MCP — already done by Milestone 2. Wins the "LLM controls robot via camera" ask alone.
- **T1:** + SmolVLA autonomy with live language-goal switching.
- **T2 (hero):** + the full preempt-and-correct supervisor. Demo the moment the VLA fails and Claude saves it.

---

## Demo script (the 2-minute win)

1. "Claude, pick up the red block and drop it in the cup." → Claude sets the VLA goal, narrates.
2. VLA starts moving. **You move the cup mid-run** (induce failure). VLA keeps reaching for empty space.
3. Claude (watching the frame): "The cup moved; the policy is reaching the old location. Pausing." → `pause_vla` → `move_joints` to re-align over the new cup position → `resume_vla`.
4. Task completes. Claude: "Done — recovered from the displacement."
5. One-line pitch: *"The VLA is the reflexes; Claude is the supervisor that notices when the reflexes are wrong."*

---

## Protocol reference (confirmed from `norma-core` protobufs)

- **Camera:** queue `usb-video` → `FramesPack{format{width,height,kind}, frames_data[], linear_data}`; `kind` FF_JPEG(1) or FF_NCHW(0). Decode JPEG with PIL.
- **Joints:** queue `st3215/inference` → `InferenceState{position,current,temperature,voltage,...}` per motor, 6 motors (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper).
- **Command:** `DriverCommand{type:STC_ST3215_COMMAND, body: ST3215Command{target_bus_serial, write:ST3215WriteCommand{motor_id, address:0x2A, value:int.to_bytes(2,"little")}}}` → `send_commands(client,[cmd])`. Position register = **0x2A**.
- **VLA bridge:** `inference/normvla`, shm `/dev/shm/normvla`, runner `software/ai/smolvla_py/scripts/run_policy.py` (`--checkpoint --task --server --bus-serial --auto`). Patch: move task tokenization inside the loop, read goal from file.
- **CONFIRM ON HARDWARE (research-inferred, verify in Milestone 0):** exact `usb-video` queue id, the `station_py` client import path, and the normvla obs frame layout. Check `station_data/.../inference/normvla/wal/` if undocumented.

## Launch commands

```bash
# Robot host: run the station
./station --config station.yaml --web

# Laptop GPU: fast brain (after patching run_policy.py)
cd norma-core/software/ai/smolvla_py
uv run python scripts/run_policy.py --checkpoint lerobot/smolvla_base \
  --task "$(cat vla_goal.txt)" --server localhost --bus-serial <FROM_UI> --auto

# Supervisor: Claude Code as the slow brain
claude --dangerously-skip-permissions --system-prompt-file CLAUDE-FABLE-5.md
```

> Note on `--dangerously-skip-permissions`: fine for the live demo since the **safety envelope lives in the MCP server** (every motion is clamped to joint/velocity/workspace limits server-side), so the model physically cannot command an unsafe move even with prompts disabled.

## Risks & mitigations
- **SmolVLA weak zero-shot** → that's the supervisor's job; plus Milestone 5 fine-tune; plus T0 fallback (Claude direct teleop) never needs the VLA.
- **Protocol mismatch** → Milestone 0 verifies against live hardware before any code depends on it.
- **Loop too slow for live correction** → small frames, terse state, supervisor at ~0.3 Hz over a 10 Hz VLA; correction is "pause → reposition → resume," not real-time servoing.
- **Hardware/serial flakiness** → record a backup demo video at Milestone 6.
