#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "${BASH_SOURCE[0]}")/../readme_eval_checks/fixtures.py" new-cli 01-write-new-cli
