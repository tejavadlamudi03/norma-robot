"""station_mcp — MCP server exposing the ElRobot to a Claude Code supervisor.

Tools (the supervisor's hands and eyes):
  observe()              -> camera image(s) + normalized joint state  [read-only]
  get_joint_state()      -> joint vector only, no image               [read-only]
  move_joints(targets)   -> atomic sync-write, normalized [0,1]       [motion]
  set_gripper(value)     -> open/close gripper                        [motion]
  set_vla_goal(text)     -> hand the SmolVLA fast-brain a new goal
  pause_vla()/resume_vla()-> suspend/resume the reactive policy
  vla_status()           -> current goal + paused flag

Safety envelope (enforced HERE, not in the model):
  - normalized targets clamped to [0,1]
  - per-call motion clamped to MAX_STEP from the current position (no violent jumps)
  - refuses to move uncalibrated joints (range_min == range_max)
  - unspecified joints hold their current position (sync-write needs all motors)

Run:  uv run --python .venv/bin/python station_mcp.py
(usually launched for you by Claude Code via .mcp.json)
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import time
from pathlib import Path

from PIL import Image as PILImage
from mcp.server.fastmcp import FastMCP, Image

import robot_lib as rl

# --- config (override via env) ----------------------------------------------
STATION_HOST = os.environ.get("STATION_HOST", "localhost")
MAX_STEP = float(os.environ.get("ROBOT_MAX_STEP", "0.25"))      # max normalized move per call
IMG_MAX_W = int(os.environ.get("ROBOT_IMG_MAX_W", "512"))       # downscale frames for token budget
GRIPPER_NAME = os.environ.get("ROBOT_GRIPPER_JOINT", "")  # set once identified (e.g. "j8")
_STATE_DIR = Path(os.environ.get("ROBOT_STATE_DIR", Path(__file__).resolve().parent))
VLA_GOAL_FILE = _STATE_DIR / "vla_goal.txt"
VLA_PAUSE_FILE = _STATE_DIR / "vla_pause"      # presence = paused
SKILLS_DIR = _STATE_DIR / "skills"             # Claude's self-built primitive library
SKILLS_DIR.mkdir(exist_ok=True)

mcp = FastMCP("robot-station")

# --- lazily-initialised shared station connection ---------------------------
_cli = None
_bus = None
_lock = asyncio.Lock()

# --- in-flight trajectory buffer (full 8-joint norm vectors actually commanded)
_trajectory: list[list[float]] = []


async def _ensure() -> tuple[object, str]:
    """Connect (and reconnect) to the station; cache client + bus serial.
    Drops a dead handle so a station restart self-heals without a /mcp reconnect."""
    global _cli, _bus
    async with _lock:
        if _cli is not None and not getattr(_cli, "connected", False):
            _cli = None  # station was restarted -> stale handle, drop it
        if _cli is None:
            _cli = await rl.connect(STATION_HOST)
            _bus = await rl.discover_bus_serial(_cli)
    return _cli, _bus


async def _retry(fn):
    """Run an async station op; on a connection drop, reconnect once and retry."""
    try:
        return await fn()
    except Exception as e:
        if "NotConnected" in type(e).__name__ or "onnect" in str(e) or "no frame" in str(e):
            global _cli
            _cli = None
            await _ensure()
            return await fn()
        raise


def _downscale_jpeg(jpeg: bytes) -> bytes:
    with PILImage.open(io.BytesIO(jpeg)) as im:
        im = im.convert("RGB")
        if im.width > IMG_MAX_W:
            h = round(im.height * IMG_MAX_W / im.width)
            im = im.resize((IMG_MAX_W, h))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=72)
        return buf.getvalue()


def _state_text(obs: dict, bus: str) -> str:
    lines = [f"bus={bus}  frame={obs['frame_id'].hex()[:12]}  vla={_vla_status_str()}",
             f"{'joint':>11} {'norm':>6} {'raw':>6} {'range':>13} cal"]
    for j in obs["joints"]:
        cal = "n" if (j["range_min"] == j["range_max"]) else "y"
        lines.append(f"{j['name']:>11} {j['pos_norm']:>6.3f} {j['pos']:>6} "
                     f"[{j['range_min']:>5},{j['range_max']:>5}] {cal}")
    return "\n".join(lines)


def _vla_status_str() -> str:
    paused = VLA_PAUSE_FILE.exists()
    goal = VLA_GOAL_FILE.read_text().strip() if VLA_GOAL_FILE.exists() else "(none)"
    return f"{'PAUSED' if paused else 'running'} goal={goal!r}"


# ===========================================================================
# Perception

@mcp.tool(annotations={"readOnlyHint": True})
async def observe() -> list:
    """Capture a FRESH camera frame + the current joint state. Call this at the
    start of every supervisory cycle — never reason from a stale frame.
    Returns BOTH camera views (each labeled) plus a text table of joint
    positions (normalized 0..1, raw ticks, calibrated range)."""
    async def go():
        cli, bus = await _ensure()
        return await rl.observe(cli), bus
    obs, bus = await _retry(go)
    labels = [
        "Camera 1 — WRIST cam (gripper jaws in the foreground; use this for FINE alignment of the gripper over the object):",
        "Camera 2 — OVERHEAD/SCENE cam (the whole table: the object on the white sheet and the labeled bins; use this for WHERE things are):",
    ]
    out: list = []
    for i, jpeg in enumerate(obs["images"]):
        out.append(labels[i] if i < len(labels) else f"Camera {i + 1}:")
        out.append(Image(data=_downscale_jpeg(jpeg), format="jpeg"))
    out.append(_state_text(obs, bus))
    return out


@mcp.tool(annotations={"readOnlyHint": True})
async def get_joint_state() -> str:
    """Return the joint vector only (no image) — cheap, for quick progress checks."""
    async def go():
        cli, bus = await _ensure()
        return await rl.observe(cli), bus
    obs, bus = await _retry(go)
    return _state_text(obs, bus)


# ===========================================================================
# Motion (safety envelope enforced here)

@mcp.tool(annotations={"destructiveHint": True})
async def move_joints(targets: dict[str, float], max_velocity: float | None = None) -> str:
    """Move joints to ABSOLUTE normalized targets in [0,1]. `targets` maps joint
    name -> target, e.g. {"j3":0.4, "j7":0.0}. This 8-DOF arm's joints are j1..j8:
      j1 = base rotation (swing left/right),  j2 = shoulder (reach up/down),
      j3 = elbow (extend/retract),            j4,j5,j6 = wrist orientation,
      j7 = GRIPPER (1.0 open, 0.0 closed),    j8 = wrist/extra.
    (Roles for j4–j6,j8 are approximate — discover their effect by nudging one
    joint a little and re-observing.) Unspecified joints HOLD position. Each joint
    moves at most ~0.25 normalized per call (server-clamped); bigger requests are
    clamped, not rejected, so make several small moves and re-observe between them.
    Re-issuing the same target is safe. Returns the resulting joint state."""
    cli, bus = await _ensure()
    obs = await rl.observe(cli)
    joints = obs["joints"]
    by_name = {j["name"]: j for j in joints}

    unknown = [k for k in targets if k not in by_name]
    if unknown:
        raise ValueError(f"unknown joints {unknown}; valid: {list(by_name)}")

    motor_ids, goals, ranges = [], [], []
    for idx, j in enumerate(joints):
        cur = j["pos_norm"]
        if j["name"] in targets:
            if j["range_min"] == j["range_max"]:
                raise ValueError(f"joint {j['name']} is not calibrated — run autocalibration first")
            want = max(0.0, min(1.0, float(targets[j["name"]])))
            # clamp step magnitude
            want = max(cur - MAX_STEP, min(cur + MAX_STEP, want))
        else:
            want = cur  # hold
        motor_ids.append(rl.DEFAULT_MOTOR_IDS[idx])
        goals.append(want)
        ranges.append((j["range_min"], j["range_max"]))

    await rl.move_norm(cli, bus, motor_ids, goals, ranges)
    _trajectory.append([round(g, 4) for g in goals])  # for skill capture
    await asyncio.sleep(0.4)  # let it move before reading back
    obs2 = await rl.observe(cli)
    return "moved.\n" + _state_text(obs2, bus)


@mcp.tool(annotations={"destructiveHint": True})
async def set_gripper(value: float) -> str:
    """Set the gripper: 0.0 = closed, 1.0 = open (normalized). Returns joint state."""
    if not GRIPPER_NAME:
        raise ValueError("gripper joint not identified yet — set ROBOT_GRIPPER_JOINT "
                         "(e.g. j8) in .mcp.json after confirming which joint is the gripper")
    return await move_joints({GRIPPER_NAME: float(value)})


# ===========================================================================
# VLA supervision (file-based handshake with the patched run_policy.py)

@mcp.tool()
def set_vla_goal(text: str) -> str:
    """Give the SmolVLA fast-brain a new natural-language goal (it re-reads this
    each control cycle). This is your primary lever — prefer it over direct motion."""
    VLA_GOAL_FILE.write_text(text.strip() + "\n")
    return f"VLA goal set: {text!r}"


@mcp.tool()
def pause_vla() -> str:
    """Suspend the reactive VLA so you can issue corrective moves. Always resume_vla() after."""
    VLA_PAUSE_FILE.write_text("1")
    return "VLA paused."


@mcp.tool()
def resume_vla() -> str:
    """Resume the reactive VLA after a correction."""
    if VLA_PAUSE_FILE.exists():
        VLA_PAUSE_FILE.unlink()
    return "VLA resumed."


@mcp.tool(annotations={"readOnlyHint": True})
def vla_status() -> str:
    """Return the VLA's current goal and whether it is paused."""
    return _vla_status_str()


# ===========================================================================
# Self-built skill library — Claude's own "fast brain"
#
# Every move_joints is logged to a trajectory buffer. Once Claude has
# closed-loop-solved a sub-task, it snapshots that buffer as a NAMED skill it
# can replay fast later (no per-step LLM reasoning), then verify with observe().

def _skill_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_").strip("-_")
    if not safe:
        raise ValueError("skill name must contain letters/digits")
    return SKILLS_DIR / f"{safe}.json"


async def _step_to(cli, bus, target: list[float], ranges, tol: float = 0.02, max_iters: int = 10):
    """Drive all joints to an absolute norm target, clamped to MAX_STEP per send,
    looping until within tol (keeps replay smooth and reachable from any start)."""
    motor_ids = rl.DEFAULT_MOTOR_IDS[:len(target)]
    for _ in range(max_iters):
        obs = await rl.observe(cli)
        cur = [j["pos_norm"] for j in obs["joints"]]
        if max(abs(c - t) for c, t in zip(cur, target)) <= tol:
            return
        goals = [max(c - MAX_STEP, min(c + MAX_STEP, t)) for c, t in zip(cur, target)]
        await rl.move_norm(cli, bus, motor_ids, goals, ranges)
        await asyncio.sleep(0.35)


@mcp.tool()
def save_skill(name: str, description: str = "") -> str:
    """Snapshot the motions you've made since the last save/clear as a reusable,
    replayable skill (a sequence of joint poses). Call this right after you
    closed-loop-solved a sub-task, so you can replay_skill(name) fast next time."""
    if not _trajectory:
        return "no motions recorded since last save/clear — nothing to save."
    data = {"name": name, "description": description,
            "waypoints": list(_trajectory), "joints": rl.JOINT_NAMES}
    _skill_path(name).write_text(json.dumps(data, indent=2))
    n = len(_trajectory)
    _trajectory.clear()
    return f"saved skill {name!r} with {n} waypoints. Trajectory buffer cleared."


@mcp.tool()
def list_skills() -> str:
    """List the skills Claude has built so far (name, description, #waypoints)."""
    out = []
    for p in sorted(SKILLS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            out.append(f"- {d['name']}: {d.get('description','')} ({len(d['waypoints'])} waypoints)")
        except Exception:
            continue
    return "\n".join(out) if out else "(no skills saved yet)"


@mcp.tool()
def clear_trajectory() -> str:
    """Discard the current (unsaved) trajectory buffer without saving a skill."""
    n = len(_trajectory)
    _trajectory.clear()
    return f"cleared {n} unsaved waypoints."


@mcp.tool(annotations={"destructiveHint": True})
async def replay_skill(name: str) -> str:
    """Replay a saved skill fast (no per-step reasoning), then return the final
    joint state so you can observe() and correct only if needed. Each step keeps
    the normal safety clamp, so replay is smooth and reachable from any pose."""
    p = _skill_path(name)
    if not p.exists():
        raise ValueError(f"no skill named {name!r}. Available: "
                         f"{[q.stem for q in SKILLS_DIR.glob('*.json')]}")
    skill = json.loads(p.read_text())
    cli, bus = await _ensure()
    obs = await rl.observe(cli)
    ranges = [(j["range_min"], j["range_max"]) for j in obs["joints"]]
    if any(rmin == rmax for rmin, rmax in ranges):
        raise ValueError("some joints uncalibrated — run autocalibration before replay")
    t0 = time.time()
    for wp in skill["waypoints"]:
        await _step_to(cli, bus, wp, ranges)
    obs2 = await rl.observe(cli)
    return (f"replayed {name!r} ({len(skill['waypoints'])} waypoints, "
            f"{time.time()-t0:.1f}s).\n" + _state_text(obs2, bus))


if __name__ == "__main__":
    mcp.run()
