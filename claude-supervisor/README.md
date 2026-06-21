# Claude Supervisor — controlling the ElRobot arm with an LLM

**Berlin AI × Robotics hackathon · NormaCore "AI-Powered Robot Control" track**

A [Claude](https://claude.com/claude-code) session drives NormaCore's 8-DOF **ElRobot** arm to do a real **pick-and-place** (pick a carrot off a sheet → drop it in a box), and supervises a fast **SmolVLA** policy — watching the cameras, setting the policy's goal, and **preempting it with direct joint commands when it fails**. Built on top of the NormaCore station in this repo.

## The idea: two brains, two speeds

```
   ┌──────────────────────────┐         ┌───────────────────────────────┐
   │  SLOW brain  (~0.3 Hz)    │         │  FAST brain  (~10 Hz)         │
   │  Claude Code session      │         │  SmolVLA policy (GPU)         │
   │  perceive → judge → act   │         │  observation → motor action   │
   └──────────┬───────────────┘         └───────────────┬───────────────┘
              │  MCP tools (station_mcp.py)              │  inference/normvla
              └──────────────────┬───────────────────────┘
                                 ▼
                    NormaCore  station  (normfs, TCP :8888)
                       ST3215 servo bus  +  USB cameras
                                 ▼
                          ElRobot 8-DOF arm
```

- **Fast brain** = SmolVLA running on the `inference/normvla` bridge — reactive, high-rate, but brittle.
- **Slow brain** = Claude — reasons over the camera + joint state, and when the policy stalls or grasps wrong, **pauses it and issues a corrected joint move**. (Novelty: runtime *preempt-and-correct*, not plan-time prompting.)
- Claude can also run the whole pick-and-place itself, **no policy needed** — that's the reliable demo.

## How Claude actually controls the arm

| Piece | File | Role |
|---|---|---|
| **MCP server** | `station_mcp.py` | Claude's tool interface: `observe`, `move_joints`, `set_gripper`, `pause_vla`… **All safety limits (joint/step clamps) live here, not in the model.** |
| **Control layer** | `robot_lib.py` | Thin wrapper over the station: connect, observe (camera+joints), atomic sync-write moves, and **`current_st3215`** — reads joint state straight off the **motor bus**, so motion never stalls when the camera feed drops. |
| **Learned IK** | `grasp_model.py` + `grid_grasp.json` | Bilinear interpolation over a **taught 3×3 grid** of grasp poses → a joint target for any `(u,v)` spot on the sheet. No analytic kinematics. |
| **Pick-and-place** | `smooth_pick.py` | The motion executor: `approach → grip → lift → carry → drop → home`, all as one autonomous, **overload-safe** run. |
| **Teaching** | `teach_points.py`, `teach_drop.py` | Record grasp/drop poses by hand-guiding the arm (motor-bus recorder, freeze-proof). |

### Two things that made it robust
1. **Camera-independent motion.** The NormaCore camera bridge can freeze; instead of reading joint state from the camera frame, motion drives off the live **ST3215 motor bus** (`current_st3215`, with retries). The pick can't be blocked by a frozen feed.
2. **Overload-safe creep.** The shoulder (`j2`) faults if commanded straight to a reach pose under gravity. So every move **creeps in small steps with pauses**, and lifts by **tucking the elbow in first, then raising the shoulder** — load stays near the base, no fault.

## Run it

```bash
# 1. start the NormaCore station (arm + cameras attached) — the -t flag is required
sudo ./claude-supervisor/fix_camera_perms.sh
./station --config claude-supervisor/station.yaml -t --web        # normfs :8888, web UI :8889

# 2. drive the full pick-and-place (camera-independent, overload-safe)
NORMA_CORE_REPO=$PWD python claude-supervisor/smooth_pick.py pickdrop <u> <v>
#   approach -> grip -> lift -> carry to box -> drop -> come up -> home

# 3. (optional) launch Claude as the live supervisor — APPEND the prompt, never replace it
claude --dangerously-skip-permissions --append-system-prompt "$(cat claude-supervisor/SUPERVISOR.md)"
```

> `robot_lib.py` imports the station's Python client from this repo. Set `NORMA_CORE_REPO` to the repo root (where `software/` and `target/gen_python/` live) so the generated protobufs resolve.

## More

- `PLAN.md` — full plan, demo script, fallback tiers.
- `SUPERVISOR.md` — Claude's control-loop system prompt (perceive → judge → act → verify; preempt-and-correct).
- `CLAUDE.md` — engineering notes: normfs protocol, hardware gotchas (gripper = `j8`, `j7` = rotation; `j2` overload), the manual-pick pipeline.
- `grasp_offsets.md`, `pick_recipe.json` — the grasp corrections + gripper/lift constants learned on hardware.
