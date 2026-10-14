#!/usr/bin/env bash
# A clean branch whose delay helper adds one second to the parsed header, and a
# module docstring with a typo.
set -euo pipefail

git init -b main >/dev/null

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
MD

mkdir -p src
cat >src/retry.py <<'PY'
"""Retry helpres."""


def parse_retry_after(value):
    return int(value)
PY

git add .gitignore src/retry.py
git commit -q -m 'retry(feat) Add retry-after parsing'

git checkout -q -b feature/retry-delay
cat >>src/retry.py <<'PY'


def delay(value):
    return parse_retry_after(value) + 1
PY
git add src/retry.py
git commit -q -m 'retry(feat) Add delay helper'
