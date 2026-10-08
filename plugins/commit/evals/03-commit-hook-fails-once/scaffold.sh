#!/usr/bin/env bash
# A pre-commit hook that rejects the first commit attempt and passes the next.
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

cat >AGENTS.md <<'MD'
# Conventions

Format commit messages as `Scope(type[detail]) concise description`.
MD

printf 'greeting = "hello"\n' >app.py
git add .gitignore AGENTS.md app.py
git commit -q -m 'app(feat) Add the greeting'

hook=$(git rev-parse --git-path hooks/pre-commit)
marker=$(git rev-parse --git-path hook-failed-once)
cat >"$hook" <<HOOK
#!/bin/sh
if [ ! -e "$marker" ]; then
  : >"$marker"
  echo "pre-commit: trailing whitespace check failed, retry" >&2
  exit 1
fi
HOOK
chmod +x "$hook"

printf 'greeting = "hello, world"\n' >app.py
git add app.py
