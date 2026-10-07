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

cat >pyproject.toml <<'TOML'
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "requests>=2.28.0",
]
TOML

git add .
git commit -q -m 'Initial commit'
