#!/usr/bin/env bash
# A repository with an origin remote and an old ruff floor.
set -euo pipefail

git init -b main >/dev/null
git init --bare -b main ../origin.git >/dev/null

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

cat >pyproject.toml <<'MD'
[project]
name = "demo"
version = "0.1.0"

[dependency-groups]
dev = ["ruff>=0.1.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

printf 'x = 1\n' >app.py
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main
