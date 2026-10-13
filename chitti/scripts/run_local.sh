#!/usr/bin/env bash
# Runs the app with mocked device/audio hardware -- starts, logs, and
# waits for Ctrl-C to shut down cleanly (Milestone 1's acceptance
# criterion). No real mic/speaker/LED/mute-switch yet.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m companion_robot.app
