#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "${BASH_SOURCE[0]}")/../readme_eval_checks/fixtures.py" example-contracts 07-example-contracts
