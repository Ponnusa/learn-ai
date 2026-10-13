#!/usr/bin/env bash
# Installs chitti in editable mode with dev dependencies (pytest,
# pytest-asyncio, pyyaml). No hardware-specific setup yet -- Milestone 1
# runs entirely against mocked device/audio interfaces
# (docs/decisions/0001-milestone-0-scope.md).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -e ".[dev]"
