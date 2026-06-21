"""Set a slow, gentle goal-speed + acceleration on the follower's 8 servos.

Run before any first motion test so moves are slow regardless of how far the
policy wants to go (after calibration the servos default to max speed = 0).
No motion is commanded — this only writes the speed/accel limit registers.

    python slow_servos.py            # speed=250, accel=10 (gentle)
    SPEED=400 python slow_servos.py  # a bit faster once you trust it
"""
import asyncio, os
import robot_lib as rl
from target.gen_python.protobuf.drivers.st3215 import st3215
from target.gen_python.protobuf.station import commands, drivers
from station_py import send_commands

BUS = os.environ.get("ROBOT_BUS_SERIAL", "5B61034836")  # follower
SPEED = int(os.environ.get("SPEED", "250"))
ACCEL = int(os.environ.get("ACCEL", "10"))
RAM_GOAL_SPEED, RAM_ACC = 0x2E, 0x29


async def main():
    cli = await rl.connect(os.environ.get("STATION_HOST", "localhost"))
    cmds = []
    for mid in range(1, 9):
        for addr, val in [(RAM_GOAL_SPEED, SPEED.to_bytes(2, "little")), (RAM_ACC, bytes([ACCEL]))]:
            c = st3215.Command(target_bus_serial=BUS,
                               write=st3215.ST3215WriteCommand(motor_id=mid, address=addr, value=val))
            cmds.append(commands.DriverCommand(
                type=drivers.StationCommandType.STC_ST3215_COMMAND, body=c.encode()))
    await send_commands(cli, cmds)
    print(f"✓ follower {BUS} motors 1-8: goal_speed={SPEED}, accel={ACCEL}. No motion sent.")


if __name__ == "__main__":
    asyncio.run(main())
