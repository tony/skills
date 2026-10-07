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

printf 'uv 0.7.8\nnode 22.4.0\n' >.tool-versions

git add .
git commit -q -m 'Initial commit'
