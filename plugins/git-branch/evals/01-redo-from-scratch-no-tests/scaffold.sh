#!/usr/bin/env bash
# A clean local feature branch with a working parser and no tests, so the
# redo's no-tests refusal is the only gate in play.
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

printf '# Project\n' >README.md
git add .gitignore README.md
git commit -q -m 'docs(readme) Add the project readme'

git checkout -q -b feature/config-parser
cat >config.py <<'PY'
def parse(text):
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out
PY
git add config.py
git commit -q -m 'config(feat) Add the config parser'
