#!/usr/bin/env bash
# Runs the unit test suite (tests/unit/ only -- integration/safety/
# hardware suites have no tests yet, see each tests/*/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest tests/unit/ -v
