#!/usr/bin/env bash
# A repo whose computed sibling worktree directory already exists and is not a
# worktree, so the skill must stop instead of creating or clearing it.
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

# The sibling directory the skill computes for branch feat/collide, left
# behind by something that is not a worktree.
collide="$(pwd)-feat-collide"
mkdir -p "$collide"
echo 'user work' >"$collide/notes.txt"
