#!/usr/bin/env bash
# Push-to-talk demo: keyboard Enter to start/stop talking, real audio
# via arecord/aplay, OpenAI Whisper + TTS, writes to the same
# chitti/data/chitti.db the Parent Controls web UI reads from -- run
# that alongside this to watch memory build up live. Needs
# OPENAI_API_KEY in chitti/.env and real mic/speaker hardware.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m companion_robot.voice_loop_demo
