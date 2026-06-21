"""teach_points — record an EPISODE (home -> a point on the sheet) per label.

Flow for each point:
  1. type a label (e.g. TL, TR, MM ...) and Enter
  2. put the arm at HOME (gripper OPEN), press Enter  -> recording STARTS
  3. move the arm to the grasp pose over that point
  4. press Enter again                                -> recording SAVES
Repeat for each point. Type 'q' as the label to finish.

Saves grid_episodes.json: per label, the full trajectory + the final grasp pose.
Read-only — it never moves the arm; you move it (via the leader), it just logs.

Standard labels map to sheet coords (u: left0..right1, v: top0..bottom1):
  TL TM TR / ML MM MR / BL BM BR   (corners, edge-mids, center)

Run:  .venv/bin/python teach_points.py
"""
from __future__ import annotations
import asyncio, json
import robot_lib as rl

LABEL_UV = {
    "TL": (0.0, 0.0), "TM": (0.5, 0.0), "TR": (1.0, 0.0),
    "ML": (0.0, 0.5), "MM": (0.5, 0.5), "MR": (1.0, 0.5),
    "BL": (0.0, 1.0), "BM": (0.5, 1.0), "BR": (1.0, 1.0),
}


async def ask(prompt: str) -> str:
    return await asyncio.get_event_loop().run_in_executor(None, input, prompt)


async def record_until_enter(cli) -> list:
    frames, done = [], asyncio.Event()

    async def rec():
        while not done.is_set():
            obs = await rl.observe(cli)
            frames.append({j["name"]: round(j["pos_norm"], 4) for j in obs["joints"]})
            await asyncio.sleep(0.12)

    task = asyncio.create_task(rec())
    await ask("   ...recording — move from HOME to the point, then press Enter to SAVE: ")
    done.set()
    await task
    return frames


async def main():
    cli = await rl.connect("localhost")
    print("\nEPISODE TEACH MODE (read-only — you drive the arm).")
    data = {}
    while True:
        label = (await ask("\nLabel (TL/TM/TR/ML/MM/MR/BL/BM/BR ...), or 'q' to finish: ")).strip().upper()
        if label == "Q":
            break
        if not label:
            continue
        await ask(f"   put arm at HOME with gripper OPEN, then press Enter to START -> {label}: ")
        print(f"   ▶ recording {label} ...")
        frames = await record_until_enter(cli)
        if not frames:
            print("   (no frames captured, skipping)"); continue
        # snapshot both cameras at the final grasp pose (so Claude can see WHERE this point is)
        final = await rl.observe(cli)
        imgs = []
        for ci, jpeg in enumerate(final["images"]):
            fn = f"point_{label}_cam{ci}.jpg"
            open(fn, "wb").write(jpeg); imgs.append(fn)
        grasp = {j["name"]: round(j["pos_norm"], 4) for j in final["joints"]}
        u, v = LABEL_UV.get(label, (None, None))
        data[label] = {"u": u, "v": v, "n_frames": len(frames),
                       "grasp_pose": grasp, "images": imgs, "trajectory": frames}
        print(f"   ✔ saved {label}: {len(frames)} frames + {imgs} | grasp pose = {grasp}")
        with open("grid_episodes.json", "w") as f:    # save after each, so nothing is lost
            json.dump(data, f, indent=2)
    print(f"\nDONE — {len(data)} points saved to grid_episodes.json: {list(data)}")


if __name__ == "__main__":
    asyncio.run(main())
