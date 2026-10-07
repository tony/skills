#!/usr/bin/env bash
# One commit, then an uncommitted edit: a bakeoff's worktrees carry none of
# it, so the run must halt in non-interactive mode.
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
cat >src/sessions.py <<'PY'
"""Session store."""
CACHE = {}


def get(key):
    return CACHE.get(key)


def put(key, value):
    CACHE[key] = value
PY
git add .gitignore src/sessions.py
git commit -q -m 'sessions(feat) Add session store'

printf '# draft change\n' >>src/sessions.py
