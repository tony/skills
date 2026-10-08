#!/usr/bin/env bash
# main is checked out; feature/limits, holding one wip commit, is not.
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
printf 'def sync():\n    return 0\n' >src/sync.py
printf '# Project\n' >README.md
git add .gitignore src/sync.py README.md
git commit -q -m 'sync(feat) Add the sync command'

git checkout -q -b feature/limits
printf 'def limit():\n    return 5\n' >src/limits.py
printf '# Project\n\nRate limits apply.\n' >README.md
git add src/limits.py README.md
git commit -q -m 'wip stuff'
git checkout -q main
