#!/usr/bin/env bash
# Launches the demo full-screen on whatever display is attached (the
# real HDMI output once this moves onto the Pi 5). Needs
# ANTHROPIC_API_KEY in story_stage/.env -- copy .env.example first.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run story-stage --fullscreen "$@"
