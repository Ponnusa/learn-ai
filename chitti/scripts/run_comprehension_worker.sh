#!/usr/bin/env bash
# Decision 0131: headless background worker that generates
# comprehension questions for parent-uploaded reading exercises --
# polls the same chitti/data/chitti.db the Parent Controls web UI and
# voice_loop_demo.py both use, so a parent sees generated questions to
# review next time they open Parent Controls, independent of whether
# Chitti's own device is even running. Needs OPENAI_API_KEY in
# chitti/.env (same as voice_loop_demo.py) -- NOT needed by
# parent_controls/app.py itself, which never imports an LLM backend.
# Run this under cron or a systemd timer on the Pi, separate from
# both run_voice_loop_demo.sh and run_parent_controls.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m companion_robot.parent_controls.comprehension_worker
