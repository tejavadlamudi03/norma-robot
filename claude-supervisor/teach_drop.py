"""teach_drop — record the carrot-drop path by teleop + keyboard marks.

Teleop the arm to each key spot, then type a label + Enter to snapshot the
current pose (read LIVE off the motor bus — camera-independent, no Claude in the
loop). Type 'done' to save. Writes drop_path.json as an ORDERED list of
waypoints the drop motion will pass through, after the pick, while holding the
carrot:  home -> (waypoints in order) -> open jaws at the last one -> home.

Usage:
    .venv/bin/python teach_drop.py

Suggested marks (in order):
    up        the raised/carry pose right after leaving home (carrot clears table)
    over_box  positioned above the box, ready to release  <-- jaws open HERE
"""
from __future__ import annotations
import asyncio, json
import robot_lib as rl

OUT = "drop_path.json"


async def main():
    cli = await rl.connect("localhost")
    waypoints = []
    print("\n=== TEACH DROP ===")
    print("Teleop the arm to a spot, then type a label + Enter to snapshot it.")
    print("Suggested order:  up  ->  over_box   (the LAST mark is where jaws open).")
    print("Type 'done' (or just Enter) to finish.\n")
    while True:
        label = (await asyncio.to_thread(input, "mark label (or 'done'): ")).strip()
        if label.lower() in ("done", "q", "quit", ""):
            break
        cur, _ = await rl.current_st3215(cli)
        pose = {k: round(v, 4) for k, v in cur.items()}
        waypoints.append({"label": label, "pose": pose})
        print(f"  ✓ marked '{label}': { {k: round(v,2) for k,v in pose.items()} }\n")
    if not waypoints:
        print("no waypoints marked — nothing saved.")
        return
    json.dump(waypoints, open(OUT, "w"), indent=2)
    print(f"\nsaved {len(waypoints)} waypoints -> {OUT}")
    for i, w in enumerate(waypoints):
        tag = "  (jaws OPEN here)" if i == len(waypoints) - 1 else ""
        print(f"  {i+1}. {w['label']}{tag}")


if __name__ == "__main__":
    asyncio.run(main())
