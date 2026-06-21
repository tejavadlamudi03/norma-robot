"""smooth_pick — overload-safe pick driven by the LIVE motor bus (camera-independent).

Reads joint positions straight from st3215/inference (never freezes when the
usb-video/normvla camera feed drops), creeps in small steps with pauses (no
torque spikes), auto-relieves shoulder stalls, and ALWAYS carries the carrot
HOME after lifting.

Recipe: gripper = j8 (open ~0.78, CLOSE until it clamps ~0.22); rotation j7~0.45;
lift = retract j3 + pitch j4 up; then go home holding the grip.

Usage:
    .venv/bin/python smooth_pick.py home              # creep to home (jaws open)
    .venv/bin/python smooth_pick.py approach <u> <v>  # home -> creep to approach pose, stop
    .venv/bin/python smooth_pick.py grip              # close jaws -> lift -> carry HOME
Env: STEP (default 0.03), DT (default 0.5).
"""
from __future__ import annotations
import asyncio, os, sys
import robot_lib as rl
from grasp_model import grasp_pose

BUS = "5B61034836"
STEP = float(os.environ.get("STEP", "0.03"))
DT = float(os.environ.get("DT", "0.5"))
JN = rl.JOINT_NAMES
HOME = {"j1": 0.526, "j2": 0.027, "j3": 0.443, "j4": 0.981,
        "j5": 0.532, "j6": 0.581, "j7": 0.45, "j8": 0.78}
GRIP_CLOSED = 0.18   # fully-closed target; stalls earlier on an object


async def read(cli):
    """Live joint norms + ranges from the motor bus (camera-independent)."""
    return await rl.current_st3215(cli)


async def goto(cli, target, step=STEP, dt=DT, tol=0.02, max_iter=400, relieve=True):
    """Creep every joint toward target in small steps. If progress stalls
    (error stops decreasing => shoulder overload), retract j3 to relieve, resume."""
    motor_ids = rl.DEFAULT_MOTOR_IDS
    prev = None; stall = 0
    for _ in range(max_iter):
        cur, ranges = await read(cli)
        err = max(abs(cur[n] - target.get(n, cur[n])) for n in JN)
        if err <= tol:
            return True
        if prev is not None and err >= prev - 0.004:
            stall += 1
        else:
            stall = 0
        prev = err
        if relieve and stall >= 4:
            print("   ! stall/overload — retracting j3 to relieve")
            for _ in range(6):
                cur, ranges = await read(cli)
                g = [max(0.05, cur["j3"] - step) if n == "j3" else cur[n] for n in JN]
                await rl.move_norm(cli, BUS, motor_ids, g, ranges)
                await asyncio.sleep(dt)
            stall = 0; prev = None
            continue
        g = [cur[n] + max(-step, min(step, target.get(n, cur[n]) - cur[n])) for n in JN]
        await rl.move_norm(cli, BUS, motor_ids, g, ranges)
        await asyncio.sleep(dt)
    return False


async def close_gripper(cli, target=GRIP_CLOSED, step=STEP, dt=DT, max_iter=60):
    """Close j8 until fully closed OR it stalls on the object (= a real grip)."""
    motor_ids = rl.DEFAULT_MOTOR_IDS
    prev = None; stall = 0
    for _ in range(max_iter):
        cur, ranges = await read(cli)
        if cur["j8"] <= target:
            print(f"   jaws fully closed (j8={cur['j8']:.2f})"); return
        if prev is not None and abs(cur["j8"] - prev) < 0.004:
            stall += 1
            if stall >= 2:
                print(f"   jaws stalled on object — GRIPPED (j8={cur['j8']:.2f})"); return
        else:
            stall = 0
        prev = cur["j8"]
        g = [max(target, cur["j8"] - step) if n == "j8" else cur[n] for n in JN]
        await rl.move_norm(cli, BUS, motor_ids, g, ranges)
        await asyncio.sleep(dt)


async def do_approach(cli, u, v):
    """Creep home, then to the taught-grid grasp pose for (u,v), jaws open."""
    print("Step 0: creep to HOME first ...")
    await goto(cli, HOME)
    appr = grasp_pose(u, v); appr["j8"] = 0.78; appr["j7"] = 0.45
    print(f"Step 1: creep to APPROACH pose (u={u}, v={v}), jaws open:")
    print("  ", {k: round(x, 3) for k, x in appr.items()})
    await goto(cli, appr)


async def do_grip(cli):
    """Close jaws on the carrot, lift it clear (2-stage, no overload), carry HOME."""
    print("GRIP — closing jaws (j8) until they clamp ...")
    await close_gripper(cli)
    # LIFT 1: tuck elbow in + wrist up — raises a bit + pulls load near the base.
    print("LIFT 1 — tuck elbow (j3) in + wrist (j4) up ...")
    cur, _ = await read(cli)
    tuck = dict(cur); tuck["j3"] = max(0.10, cur["j3"] - 0.30); tuck["j4"] = min(0.95, cur["j4"] + 0.30)
    await goto(cli, tuck)
    # LIFT 2: now tucked, raise shoulder (j2 DOWN = fold up) to clear the ground.
    print("LIFT 2 — raise shoulder (j2) to clear the ground ...")
    cur, _ = await read(cli)
    clear = dict(cur); clear["j2"] = min(cur["j2"], 0.15)
    await goto(cli, clear)
    print("HOME — carrying the carrot home, up high (jaws stay closed) ...")
    cur, _ = await read(cli)
    hg = dict(HOME); hg["j8"] = cur["j8"]   # keep current grip while homing
    await goto(cli, hg)
    print("done — at home, holding the carrot.")


async def do_drop(cli, path="drop_path.json"):
    """Carry the held carrot to the box along the taught waypoints, open the jaws
    to drop, then RETRACE the same waypoints in reverse back to HOME (so the arm
    backs out of the box cleanly instead of swinging through it).
    Path =  home -> [carry-in legs] -> [drop pose: open jaws] -> [carry-in reversed] -> HOME."""
    import json
    wps = json.load(open(path))
    poses = {w["label"]: w["pose"] for w in wps}
    order = [w["label"] for w in wps]
    OPEN_TH = 0.6  # taught j8 >= this == jaws were open at that mark == the drop point
    fwd = [l for l in order if poses[l]["j8"] < OPEN_TH]                      # e.g. up, over_box
    drop_label = next((l for l in order if poses[l]["j8"] >= OPEN_TH), None)  # e.g. jaws_open
    cur, _ = await read(cli)
    grip = cur["j8"]                                                          # hold the carrot at the current grip
    print(f"DROP — carrying the carrot to the box (holding j8={grip:.2f}) ...")
    for l in fwd:                                                             # home -> up -> over_box
        print(f"   -> {l}")
        p = dict(poses[l]); p["j8"] = grip
        await goto(cli, p)
    if drop_label:
        print(f"   -> {drop_label}: settle over the box, then OPEN jaws (drop) ...")
        p = dict(poses[drop_label]); p["j8"] = grip                          # settle in drop pose still holding
        await goto(cli, p)
        op = dict(poses[drop_label]); op["j8"] = 0.95                        # open -> carrot falls into box
        await goto(cli, op)
    # RETURN HOME (overload-safe). The arm is extended out over the box; asking the
    # shoulder (j2) to lift it straight up stalls (gravity torque). So use the SAME
    # proven recipe as the pick lift: first TUCK the elbow (j3) in — which both
    # relieves the shoulder AND pulls the arm back OFF the box (toward the base) —
    # THEN raise the shoulder, THEN go home. This avoids the box and never overloads.
    print("   backing off the box: small pull-back to over_box (jaws open) ...")
    if fwd:                                                                  # fwd[-1] == over_box
        ob = dict(poses[fwd[-1]]); ob["j8"] = 0.95
        await goto(cli, ob)
    print("   lift-clear: tuck elbow (j3) in + wrist up (pulls back off the box) ...")
    cur, _ = await read(cli)
    tuck = dict(cur); tuck["j3"] = max(0.08, cur["j3"] - 0.28); tuck["j4"] = min(0.95, cur["j4"] + 0.18); tuck["j8"] = 0.95
    await goto(cli, tuck)
    print("   raise shoulder (j2) up, clear of the box ...")
    cur, _ = await read(cli)
    clear = dict(cur); clear["j2"] = min(cur["j2"], 0.20); clear["j8"] = 0.95
    await goto(cli, clear)
    print("   -> HOME")
    hg = dict(HOME); hg["j8"] = 0.95
    await goto(cli, hg)
    print("done — carrot dropped in the box, came up clear and back home.")


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pick"
    cli = await rl.connect("localhost")

    if cmd in ("home", "homegrip"):
        target = dict(HOME)
        if cmd == "homegrip":
            target["j8"] = 0.22
        print(f"creeping to HOME{' (holding carrot)' if cmd == 'homegrip' else ''} ...")
        await goto(cli, target)
        print("at home.")
        return

    if cmd == "grip":
        await do_grip(cli)
        return

    if cmd == "drop":
        await do_drop(cli)
        return

    if cmd == "pickdrop":   # fully autonomous: approach -> grip -> carry -> drop -> home
        u, v = float(sys.argv[2]), float(sys.argv[3])
        await do_approach(cli, u, v)
        await do_grip(cli)
        await do_drop(cli)
        return

    # cmd == "approach" (or "pick")
    u, v = float(sys.argv[2]), float(sys.argv[3])
    await do_approach(cli, u, v)
    print("approach reached — verify/fine-tune, then `smooth_pick.py grip`, then `smooth_pick.py drop`.")


if __name__ == "__main__":
    asyncio.run(main())
