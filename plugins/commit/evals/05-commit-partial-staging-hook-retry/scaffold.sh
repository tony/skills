#!/usr/bin/env bash
# app.py is partially staged; a hook rewrites it and rejects the first attempt.
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

printf 'a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\nh = 8\ni = 9\nj = 10\n' >app.py
git add .gitignore AGENTS.md app.py
git commit -q -m 'app(feat) Add constants'

printf 'a = 11\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\nh = 8\ni = 9\nj = 12\n' >app.py
printf 'y\nn\n' | git add -p app.py >/dev/null

hook=$(git rev-parse --git-path hooks/pre-commit)
marker=$(git rev-parse --git-path hook-failed-once)
cat >"$hook" <<HOOK
#!/bin/sh
if [ ! -e "$marker" ]; then
  : >"$marker"
  sed -i.bak 's/^a = 11/a = 11  # formatted/' app.py && rm -f app.py.bak
  echo "pre-commit: formatter rewrote app.py, retry" >&2
  exit 1
fi
HOOK
chmod +x "$hook"
