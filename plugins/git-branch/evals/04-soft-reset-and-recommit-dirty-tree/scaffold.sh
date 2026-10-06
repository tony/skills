#!/usr/bin/env bash
# A feature branch with one wip commit and an uncommitted edit, so the
# dirty-tree gate has something to refuse on.
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
printf 'def sync():\n    return 1\n\n\ndef limit():\n    return 5\n' >src/sync.py
printf '# Project\n\nRate limits apply.\n' >README.md
git add src/sync.py README.md
git commit -q -m 'wip stuff'

printf '\n# unfinished\n' >>src/sync.py
