#!/usr/bin/env bash
set -euo pipefail

git init -q -b main .

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

printf '# demo\n\nNo manifests here.\n' >README.md

git add .
git commit -q -m 'Initial commit'
