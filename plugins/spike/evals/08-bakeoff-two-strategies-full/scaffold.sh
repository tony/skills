#!/usr/bin/env bash
# A clean repository with one commit and an unbounded cache, so two cheap
# strategies exist and a clean tree lets the bakeoff run end to end.
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
cat >src/cache.py <<'PY'
"""In-memory cache that never evicts."""
_STORE = {}


def get(key):
    return _STORE.get(key)


def put(key, value):
    _STORE[key] = value
PY
git add .gitignore src/cache.py
git commit -q -m 'cache(feat) Add in-memory cache'
