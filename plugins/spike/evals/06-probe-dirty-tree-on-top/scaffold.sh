#!/usr/bin/env bash
# One commit, then an uncommitted edit to a tracked file and an untracked
# file: the user's work a probe on top must leave in the tree untouched.
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
cat >src/durations.py <<'PY'
"""Duration parsing."""

UNITS = {"s": 1, "m": 60, "h": 3600}


def parse_duration(text):
    unit = text[-1]
    return int(text[:-1]) * UNITS[unit]
PY
printf 'draft notes\n' >notes.txt

git add .gitignore src/durations.py notes.txt
git commit -q -m 'durations(feat) Add parse_duration'

printf 'unsaved edit\n' >>notes.txt
printf 'scratch idea\n' >scratch.txt
