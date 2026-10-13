#!/usr/bin/env bash
# Runs the Parent Controls web UI standalone, reachable from any device
# on the same LAN -- visit http://<this-device's-IP>:5000/ from a
# phone or laptop on the same WiFi network. Never expose this port
# beyond the LAN (no port-forwarding), per decision 0002's design.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m companion_robot.parent_controls.app
