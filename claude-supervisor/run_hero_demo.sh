#!/usr/bin/env bash
# Turnkey setup for the hero demo: Claude (supervisor) overseeing the SmolVLA.
# RUN THIS ONLY WHEN YOU ARE WATCHING THE ARM (it starts autonomous motion).
#
# It: frees the GPU (stops training+watchdog), sets gentle speed, starts the VLA
# in the background (obeys vla_goal.txt + vla_pause), and prints how to launch
# the Claude supervisor. Resume training afterward with ./resume_training.sh.
set -euo pipefail
DIR="/home/manas-reddy/Downloads/Normacore hackthon"
SMOL="$DIR/norma-core/software/ai/smolvla_py"
cd "$DIR"

# newest checkpoint (most trained)
CKPT="$(ls -dt "$DIR"/smolvla_ckpt/final "$DIR"/smolvla_ckpt/step-* 2>/dev/null | head -1 || true)"
[ -n "${CKPT:-}" ] || { echo "no checkpoint in smolvla_ckpt/"; exit 1; }

echo "==> freeing GPU (stopping training + watchdog)"
pkill -f "watchdog.sh" 2>/dev/null || true
pkill -9 -f "scripts/train.py" 2>/dev/null || true
sleep 5

echo "==> station check"
if ! timeout 2 bash -c 'cat </dev/null >/dev/tcp/localhost/8888' 2>/dev/null; then
  echo "   station DOWN. Start it (after sudo ./fix_camera_perms.sh if cams were replugged):"
  echo "     ./station --config station.yaml -t --web"
  exit 1
fi

echo "==> gentle servo speed (no motion)"
SPEED=600 ACCEL=20 .venv/bin/python slow_servos.py 2>&1 | grep -v INFO || true

echo "==> goal + clear pause"
echo "sort the trash into the right bins" > vla_goal.txt
rm -f vla_pause

echo "==> starting VLA (background) on $(basename "$CKPT")  [arm will move]"
cd "$SMOL"
nohup env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True .venv/bin/python -u scripts/run_policy_supervised.py \
  --checkpoint "$CKPT" --task "$(cat "$DIR/vla_goal.txt")" \
  --motor-ids 1,2,3,4,5,6,7,8 --server localhost --bus-serial 5B61034836 \
  --auto --max-ticks 400 --max-delta-ticks 800 > "$DIR/vla_supervised.log" 2>&1 &
echo "   VLA pid $! (log: vla_supervised.log)"

cat <<EOF

==> NOW LAUNCH THE SUPERVISOR (this terminal, fresh session loads the 8-DOF MCP server):

   claude --dangerously-skip-permissions --append-system-prompt "\$(cat "$DIR/SUPERVISOR.md")"

Then tell it the goal. It will observe -> set_vla_goal -> when the VLA freezes
(overload) or misses the grasp, pause_vla -> correct (retract j3 / close j7) -> resume_vla.

When done:  pkill -f run_policy_supervised ; ./resume_training.sh
EOF
