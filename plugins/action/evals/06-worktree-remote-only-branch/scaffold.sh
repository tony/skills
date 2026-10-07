#!/usr/bin/env bash
# A repo whose origin already holds feat/x, a branch that exists nowhere locally.
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
cat >src/sync.py <<'PY'
"""Sync command."""


def sync(source, destination):
    copied = 0
    for item in source.list():
        destination.write(item)
        copied += 1
    return copied
PY

git add .gitignore src/sync.py
git commit -q -m 'sync(feat) Add the sync command'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/x
echo 'DRY_RUN = True' >src/flags.py
git add src/flags.py
git commit -q -m 'sync(feat) Start the dry-run flag'
git push -q origin feat/x
git switch -q main
git branch -q -D feat/x
git update-ref -d refs/remotes/origin/feat/x
