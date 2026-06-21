"""station_probe — verify the live station protocol end to end.

Connects to the station, auto-discovers the ST3215 bus serial, reads one
observation frame, prints the normalized joint vector, and saves the camera
frame(s) to probe_cam0.jpg / probe_cam1.jpg so you can confirm the camera works.

Run (with the station already running and the robot connected):
    python station_probe.py                 # localhost
    python station_probe.py --server HOST    # remote station host

This makes NO motion. It is safe to run anytime.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import robot_lib as rl


async def main_async(server: str) -> None:
    print(f"connecting to station at {server}:8888 ...")
    cli = await rl.connect(server)
    print("connected.\n")

    try:
        buses = await rl.list_buses(cli)
        print(f"✓ ST3215 buses found: {len(buses)}")
        for b in buses:
            print(f"    serial={b['serial']}  port={b['port']}  "
                  f"motors={b['motor_ids']}  (n={b['n_motors']})")
        if len(buses) > 1:
            print("  ⚠ two arms (leader+follower) detected. Identify the FOLLOWER and set")
            print("    ROBOT_BUS_SERIAL=<follower_serial> in .mcp.json so we command the right one.")
        bus = await rl.discover_bus_serial(cli)
        print(f"  using bus: {bus}")
    except Exception as e:
        print(f"✗ bus discovery failed: {e}")
        bus = None

    print("\nreading one observation frame from inference/normvla ...")
    obs = await rl.observe(cli)

    print(f"✓ frame_id: {obs['frame_id'].hex()[:16]}...")
    print(f"✓ joints ({len(obs['joints'])}):")
    print(f"  {'name':>11}  {'norm':>6}  {'pos':>6}  {'range':>13}  calibrated?")
    for j in obs["joints"]:
        calibrated = not (j["range_min"] == 0 and j["range_max"] == 0)
        print(f"  {j['name']:>11}  {j['pos_norm']:>6.3f}  {j['pos']:>6}  "
              f"[{j['range_min']:>5},{j['range_max']:>5}]  {'yes' if calibrated else 'NO — run autocalibration'}")

    print(f"\n✓ camera images in frame: {len(obs['images'])}")
    for i, jpeg in enumerate(obs["images"]):
        out = Path(f"probe_cam{i}.jpg")
        out.write_bytes(jpeg)
        print(f"  saved {out}  ({len(jpeg)} bytes)")

    if not obs["images"]:
        print("  ⚠ no camera frames — check usb-video driver / camera connection.")

    print("\nprobe OK — protocol confirmed.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="localhost", help="station host (default localhost)")
    args = ap.parse_args()
    asyncio.run(main_async(args.server))


if __name__ == "__main__":
    main()
