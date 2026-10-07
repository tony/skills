#!/usr/bin/env bash
# A feature branch that adds one function; the flagged function predates it.
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
{
  echo '"""Sync helpers."""'
  echo
  echo
  echo 'def sync_all(items):'
  echo '    out = []'
  for i in $(seq 1 24); do
    echo "    out.append(items[$i % len(items)] + $i)"
  done
  echo '    return out'
} >src/sync.py

git add .gitignore src/sync.py
git commit -q -m 'sync(feat) Add sync_all'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git checkout -q -b feature/add-greeting
cat >src/greet.py <<'PY'
"""Greeting helper."""


def greet(name):
    return f"hello {name}"
PY
git add src/greet.py
git commit -q -m 'greet(feat) Add greet'
