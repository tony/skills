#!/usr/bin/env bash
# A repository whose uv config hides ruff releases younger than a cooldown.
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

cat >pyproject.toml <<'MD'
[project]
name = "demo"
version = "0.1.0"

[dependency-groups]
dev = ["ruff>=0.1.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

cat >uv.toml <<'MD'
exclude-newer = "7 days"
MD

printf 'x = 1\n' >app.py
git add .
git commit -q -m 'Initial commit'
