# Carrot grasp — systematic offsets (observed by user across runs)

The interpolation model's grasp pose lands the gripper consistently off, by the
SAME amount every run. Correction sequence (ORDER MATTERS — corrected by user):

1. **ROTATE the gripper CLOCKWISE first** (wrist-roll joint — likely `j5`/`j6`; exact joint + amount from PICK demos)
2. **then LEFT** ~3–5 cm   (in model terms: decrease `u`)
3. **then FORWARD** ~7–8 cm  (more reach; in model terms: decrease `v` → higher j2/j3)

So: gripper-rotate → left → forward, applied after the model's grasp pose.

**REFINEMENT (after first successful pick):** needs **~2-3 cm MORE LEFT (user's view)** for dead-center.
**DIRECTION FIX (confirmed on hardware):** the overhead `u`-axis is FLIPPED vs the user's left/right.
- user's-LEFT  = **INCREASE u**
- user's-RIGHT = decrease u
So the first successful pick at (u=0.33,v=0.55) was ~2-3cm to the user's-right → for dead-center
**INCREASE u to ~0.40** (NOT 0.25). (Decreasing u to 0.25 sent the gripper further user's-RIGHT — wrong way.)
Everything else (forward=lower v, rotation j7~0.45, height, grip on j8, lift) was spot-on.

Still missing (to be learned from PICK1/2/3 demos):
- how far to close `j7` to actually CLAMP the carrot (previous closes slipped),
- the LIFT motion that doesn't overload `j2` (retract elbow `j3` first, THEN raise).
