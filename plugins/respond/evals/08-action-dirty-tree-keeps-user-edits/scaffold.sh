#!/usr/bin/env bash
# A branch with an unrelated uncommitted edit that a fix must never sweep into a commit.
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
"""Retry helpers."""

def parse_retry_after(value):
    return int(value)
PY

git add .gitignore src/retry.py
git commit -q -m 'retry(feat) Add retry-after parsing'

git checkout -q -b feature/retry-fallback
cat >>src/retry.py <<'PY'

def delay(value):
    return parse_retry_after(value) + 1
PY
git add src/retry.py
git commit -q -m 'retry(feat) Add delay helper'

printf 'user scratch notes\n' >notes.txt
git add notes.txt
git commit -q -m 'docs(notes) Add notes'
printf 'half-finished thought\n' >>notes.txt
