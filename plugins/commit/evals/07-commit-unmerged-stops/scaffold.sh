#!/usr/bin/env bash
# A merge stopped on a conflict in app.py.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name Eval

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

cat >AGENTS.md <<'MD'
# Conventions

Format commit messages as `Scope(type[detail]) concise description`.
MD

printf 'greeting = "hello"\n' >app.py
git add .gitignore AGENTS.md app.py
git commit -q -m 'app(feat) Add the greeting'

git checkout -q -b topic
printf 'greeting = "hello, topic"\n' >app.py
git commit -q -am 'app(feat) Greet from topic'
git checkout -q main
printf 'greeting = "hello, main"\n' >app.py
git commit -q -am 'app(feat) Greet from main'
git merge topic >/dev/null || true
