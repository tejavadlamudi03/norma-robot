"""grasp_model — learned IK by bilinear interpolation over the taught 3x3 grid.

grasp_pose(u, v) -> {j1..j8}  where (u,v) is the sheet position
(u: left 0 .. right 1 ; v: top 0 .. bottom 1).

Built from grid_episodes.json (teach_points.py output). No motion here.
"""
from __future__ import annotations
import json

JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6", "j7", "j8"]
_US = [0.0, 0.5, 1.0]            # column coords (L, M, R)
_VS = [0.0, 0.5, 1.0]            # row coords    (T, M, B)
_COL = {0: "L", 1: "M", 2: "R"}
_ROW = {0: "T", 1: "M", 2: "B"}


def _load(path="grid_grasp.json"):
    d = json.load(open(path))
    return {lab: p["grasp_pose"] for lab, p in d.items()}


def _bracket(x, axis):
    for i in range(len(axis) - 1):
        if axis[i] <= x <= axis[i + 1]:
            return i, (x - axis[i]) / (axis[i + 1] - axis[i])
    if x < axis[0]:
        return 0, 0.0
    return len(axis) - 2, 1.0


def grasp_pose(u: float, v: float, poses=None) -> dict:
    poses = poses or _load()
    u = max(0.0, min(1.0, u)); v = max(0.0, min(1.0, v))
    ci, fu = _bracket(u, _US)       # column index + frac
    ri, fv = _bracket(v, _VS)       # row index + frac
    # 4 surrounding labels
    c00 = _ROW[ri] + _COL[ci]
    c10 = _ROW[ri] + _COL[ci + 1]
    c01 = _ROW[ri + 1] + _COL[ci]
    c11 = _ROW[ri + 1] + _COL[ci + 1]
    out = {}
    for j in JOINTS:
        top = poses[c00][j] * (1 - fu) + poses[c10][j] * fu
        bot = poses[c01][j] * (1 - fu) + poses[c11][j] * fu
        out[j] = round(top * (1 - fv) + bot * fv, 4)
    return out


if __name__ == "__main__":
    poses = _load()
    print("== reproduce taught points (should match exactly) ==")
    uv = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1), "MM": (.5, .5)}
    ok = True
    for lab, (u, v) in uv.items():
        g = grasp_pose(u, v, poses)
        err = max(abs(g[j] - poses[lab][j]) for j in JOINTS)
        print(f"  {lab} (u={u},v={v}): max err vs taught = {err:.4f}")
        ok = ok and err < 1e-3
    print("  reproduction:", "OK ✓" if ok else "MISMATCH ✗")
    print("\n== interpolated in-between poses (smoothness check) ==")
    for u, v in [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75), (0.4, 0.6)]:
        print(f"  ({u},{v}) -> {grasp_pose(u, v, poses)}")
