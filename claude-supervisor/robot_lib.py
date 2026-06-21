"""robot_lib — thin control layer over the NormaCore station for the ElRobot.

Wraps the real station_py client + generated gremlin protobufs (read from the
cloned ./norma-core checkout) into a few easy calls used by both
station_probe.py and station_mcp.py:

    cli = await connect()                      # normfs TCP :8888
    bus = await discover_bus_serial(cli)       # auto-find the ST3215 bus id
    obs = await observe(cli)                    # {frame_id, joints[], images[jpeg]}
    await move_norm(cli, bus, [1..6], goals)    # atomic sync-write, normalized [0,1]

Everything is grounded in norma-core's own examples:
  software/station/shared/station_py/example_commands.py
  software/ai/smolvla_py/scripts/run_policy.py
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
import sys
from pathlib import Path
from typing import Optional

# --- make the cloned norma-core checkout importable -------------------------
# Layout: <this dir>/norma-core  (override with NORMA_CORE_REPO env var)
_REPO = Path(os.environ.get("NORMA_CORE_REPO", Path(__file__).resolve().parent / "norma-core"))
if not _REPO.exists():
    raise SystemExit(
        f"norma-core checkout not found at {_REPO}. "
        f"Clone it there or set NORMA_CORE_REPO."
    )
sys.path.insert(0, str(_REPO))                                   # target.gen_python.*, shared.gremlin_py.*
sys.path.insert(0, str(_REPO / "software" / "station" / "shared"))  # station_py

from station_py import new_station_client, send_commands          # noqa: E402
from target.gen_python.protobuf.drivers.inferences import normvla  # noqa: E402
from target.gen_python.protobuf.drivers.st3215 import st3215       # noqa: E402
from target.gen_python.protobuf.station import commands, drivers   # noqa: E402

NORMVLA_QUEUE = "inference/normvla"
ST3215_QUEUE = "st3215/inference"
ST3215_TARGET_POS_REGISTER = 0x2A  # write target position (read present pos is 0x38)

# This ElRobot follower is 8-DOF. The normvla frame orders joints by motor id
# 1..8 (confirmed: run_policy --motor-ids 1..8 drove it correctly). Exact joint
# semantics (esp. which is the gripper) are NOT yet identified on hardware —
# do that with a gentle per-joint nudge before relying on set_gripper.
DEFAULT_MOTOR_IDS = [1, 2, 3, 4, 5, 6, 7, 8]
JOINT_NAMES = ["j1", "j2", "j3", "j4", "j5", "j6", "j7", "j8"]

_log = logging.getLogger("robot_lib")


# ---------------------------------------------------------------------------
# Connection

async def connect(server: str = "localhost"):
    """Connect to the station normfs server (default localhost:8888)."""
    return await new_station_client(server, _log)


def _as_str(v) -> str:
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).decode("utf-8", "replace")
    return str(v)


# ---------------------------------------------------------------------------
# Observation: one fresh normvla frame = camera JPEGs + normalized joint state

async def _fetch_normvla(cli, timeout: float) -> normvla.FrameReader:
    qr = cli.read_from_tail(NORMVLA_QUEUE, offset=b"\x00", limit=1, step=1, buf_size=1)
    entry = await asyncio.wait_for(qr.data.get(), timeout=timeout)
    if entry is None:
        raise RuntimeError(f"{NORMVLA_QUEUE} delivered no frame (err={qr.err}). "
                           f"Is the station running with the inference/normvla bridge?")
    return normvla.FrameReader(memoryview(bytes(entry.Data)))


async def observe(cli, timeout: float = 5.0, last_frame_id: Optional[bytes] = None) -> dict:
    """Return the latest observation.

    {
      "frame_id": bytes,
      "joints":  [{"name","pos_norm","pos","range_min","range_max"}, ...],
      "images":  [jpeg_bytes, ...]   # cam0, cam1
    }
    If last_frame_id is given, polls until a *newer* frame appears (~10 Hz).
    """
    while True:
        frame = await _fetch_normvla(cli, timeout)
        fid = bytes(frame.get_global_frame_id())
        if last_frame_id is None or fid != last_frame_id:
            break
        await asyncio.sleep(0.02)

    joints = frame.get_joints() or []
    images = [bytes(im.get_jpeg()) for im in (frame.get_images() or [])]
    out_joints = []
    for i, j in enumerate(joints):
        out_joints.append({
            "name": JOINT_NAMES[i] if i < len(JOINT_NAMES) else f"joint{i}",
            "pos_norm": round(float(j.get_position_norm()), 4),
            "pos": int(j.get_position()),
            "range_min": int(j.get_range_min()),
            "range_max": int(j.get_range_max()),
        })
    return {"frame_id": fid, "joints": out_joints, "images": images}


# ---------------------------------------------------------------------------
# Bus discovery (so the user never has to hand-copy the bus serial)

async def list_buses(cli, timeout: float = 5.0) -> list[dict]:
    """Return every ST3215 bus the station sees: serial, port, and motor IDs.
    With a leader+follower setup there are usually TWO buses — use this to tell
    them apart (the follower is the arm we command)."""
    q: asyncio.Queue = asyncio.Queue()
    cli.follow(ST3215_QUEUE, q)
    entry = await asyncio.wait_for(q.get(), timeout=timeout)
    if entry is None:
        raise RuntimeError(f"{ST3215_QUEUE} closed before delivering a bus state.")
    state = st3215.InferenceStateReader(memoryview(bytes(entry.Data)))
    buses = []
    for bus_state in (state.get_buses() or []):
        info = bus_state.get_bus()
        if not info:
            continue
        motors = bus_state.get_motors() or []
        buses.append({
            "serial": _as_str(info.get_serial_number()),
            "port": _as_str(info.get_port_name()),
            "motor_ids": [int(m.get_id()) for m in motors],
            "n_motors": len(motors),
        })
    return buses


_POS_ADDR = 0x38; _SIGN = 0x8000; _MAXA = 4095


def _norm_raw(raw: int) -> int:
    if raw & _SIGN:
        return (_MAXA + 1 - (raw & _MAXA)) & _MAXA
    return raw & _MAXA


async def current_st3215(cli, bus_serial: Optional[str] = None, timeout: float = 5.0,
                          retries: int = 5):
    """LIVE joint norms + ranges read straight from st3215/inference (the motor bus).
    Camera-independent — never freezes when the usb-video/normvla feed drops.
    Retries the WHOLE read on any transient st3215/inference glitch — a stall
    (timeout), an empty frame, a momentarily-missing follower bus, or a partial
    motor set — so a one-off gap can NOT abort an in-progress motion. Only raises
    after `retries` consecutive failures.
    Returns ({jname: norm}, [(rmin,rmax) per joint in j1..jN order])."""
    bus_serial = bus_serial or os.environ.get("ROBOT_BUS_SERIAL", "5B61034836")
    for attempt in range(retries):
        try:
            q: asyncio.Queue = asyncio.Queue()
            cli.follow(ST3215_QUEUE, q)
            e = await asyncio.wait_for(q.get(), timeout)
            if e is None:
                raise RuntimeError("st3215/inference closed")
            st = st3215.InferenceStateReader(memoryview(bytes(e.Data)))
            for bs in (st.get_buses() or []):
                info = bs.get_bus()
                if not info or _as_str(info.get_serial_number()) != bus_serial:
                    continue
                by_id = {}
                for m in (bs.get_motors() or []):
                    s = bytes(m.get_state())
                    raw = _norm_raw(struct.unpack('<H', s[_POS_ADDR:_POS_ADDR + 2])[0]) if len(s) >= _POS_ADDR + 2 else 0
                    by_id[m.get_id()] = (raw, int(m.get_range_min()), int(m.get_range_max()))
                joints = {}; ranges = []
                for i, mid in enumerate(DEFAULT_MOTOR_IDS):
                    raw, rmin, rmax = by_id[mid]   # KeyError on a partial frame -> retry
                    joints[JOINT_NAMES[i]] = round((raw - rmin) / (rmax - rmin), 4) if rmax > rmin else 0.0
                    ranges.append((rmin, rmax))
                return joints, ranges
            raise RuntimeError(f"follower bus {bus_serial} not in this frame")
        except (asyncio.TimeoutError, TimeoutError, RuntimeError, KeyError) as ex:
            if attempt == retries - 1:
                raise RuntimeError(f"st3215 read failed after {retries} tries: {ex}") from ex
            _log.warning("st3215 read glitch (attempt %d/%d): %s — retrying", attempt + 1, retries, ex)
            await asyncio.sleep(0.3)


async def discover_bus_serial(cli, timeout: float = 5.0, prefer: Optional[str] = None) -> str:
    """Return a bus serial. If ROBOT_BUS_SERIAL / `prefer` is set, use it;
    otherwise the first bus (override when both leader+follower are connected)."""
    prefer = prefer or os.environ.get("ROBOT_BUS_SERIAL")
    buses = await list_buses(cli, timeout)
    if not buses:
        raise RuntimeError("No ST3215 bus found in st3215/inference (servo bus connected?).")
    if prefer:
        for b in buses:
            if b["serial"] == prefer:
                return prefer
        raise RuntimeError(f"requested bus {prefer!r} not found; available: {[b['serial'] for b in buses]}")
    return buses[0]["serial"]


# ---------------------------------------------------------------------------
# Action: atomic sync-write of all joints, normalized [0,1] per joint

def norm_to_raw(g_norm: float, range_min: int, range_max: int) -> int:
    g = max(0.0, min(1.0, float(g_norm)))
    raw = int(round(range_min + g * (range_max - range_min)))
    return max(range_min, min(range_max, raw))


def build_sync_write(bus_serial: str, motor_ids: list[int], raw_goals: list[int]) -> "commands.DriverCommand":
    motors = [
        st3215.ST3215SyncWriteCommand_MotorWrite(
            motor_id=mid, value=int(raw).to_bytes(2, byteorder="little"),
        )
        for mid, raw in zip(motor_ids, raw_goals)
    ]
    sync = st3215.ST3215SyncWriteCommand(address=ST3215_TARGET_POS_REGISTER, motors=motors)
    cmd = st3215.Command(target_bus_serial=bus_serial, sync_write=sync)
    return commands.DriverCommand(
        type=drivers.StationCommandType.STC_ST3215_COMMAND,
        body=cmd.encode(),
    )


async def move_norm(
    cli,
    bus_serial: str,
    motor_ids: list[int],
    goals_norm: list[float],
    ranges: list[tuple[int, int]],
) -> list[int]:
    """Send one atomic sync-write moving the given motors to normalized goals.
    `ranges` are the (range_min, range_max) per motor from the latest observe().
    Returns the raw tick targets actually sent."""
    if not (len(motor_ids) == len(goals_norm) == len(ranges)):
        raise ValueError("motor_ids, goals_norm, ranges must be the same length")
    raws = [norm_to_raw(g, rmin, rmax) for g, (rmin, rmax) in zip(goals_norm, ranges)]
    await send_commands(cli, [build_sync_write(bus_serial, motor_ids, raws)])
    return raws
