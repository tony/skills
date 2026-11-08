#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "${BASH_SOURCE[0]}")/../readme_eval_checks/fixtures.py" audit-only 02-assess-existing
