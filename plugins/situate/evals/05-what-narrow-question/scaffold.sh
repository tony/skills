#!/usr/bin/env bash
# One commit on main and an edit that was never committed.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

printf 'def total(items):\n    return sum(items)\n' >calc.py
git add calc.py
git commit -q -m 'Add total helper'

printf 'def total(items):\n    return sum(items) or 0\n' >calc.py
