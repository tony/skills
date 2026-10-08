#!/usr/bin/env bash
set -euo pipefail

git init -q -b main
git config user.name eval
git config user.email eval@example.com
cat >.gitignore <<'TEXT'
.worktrees/
.scratch/
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.mcp.json
.profile
.zprofile
.zshrc
TEXT
printf 'Finished feature.\n' >README.md
git add .gitignore README.md
git commit -q -m 'Add finished feature'
git worktree add -q -b feat/finished .worktrees/finished
mkdir -p .worktrees/finished/.scratch
printf 'Unique notes kept only in this worktree.\n' >.worktrees/finished/.scratch/research.txt
