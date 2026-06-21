#!/usr/bin/env bash
# Open the two USB WORKSPACE cameras for the station (which accesses them via
# libusb, so it needs /dev/bus/usb/... not just /dev/video*).
#
# Deliberately does NOT touch the laptop's built-in webcam (3277:0010), so the
# station only captures the two workspace cameras -> cam0/cam1 match training.
#
# Run after plugging in cameras + BEFORE starting the station:
#     sudo ./fix_camera_perms.sh
# (Re-run if you replug the cameras or reboot — perms reset then.)
set -euo pipefail

# V4L2 nodes (for opencv/diagnostics)
chmod a+rw /dev/video* 2>/dev/null || true

# libusb device nodes for the 2 workspace cameras:
#   046d:0825 = Logitech C270   |   1e45:0209 = generic "USB Camera"
found=0
for vp in 046d:0825 1e45:0209; do
  while read -r bd; do
    [ -n "$bd" ] || continue
    echo "opening /dev/bus/usb/$bd  ($vp)"
    chmod a+rw "/dev/bus/usb/$bd" && found=$((found+1))
  done < <(lsusb | grep -i "$vp" | sed -E 's/Bus ([0-9]+) Device ([0-9]+).*/\1\/\2/')
done

echo "opened $found camera USB node(s). Now (re)start the station:"
echo "  ./station --config station.yaml -t --web"
