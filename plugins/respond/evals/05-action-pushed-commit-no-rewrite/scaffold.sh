#!/usr/bin/env bash
# A feature branch whose only commit is already pushed, so a fixup! would
# rewrite shared history.
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
cat >src/retry.py <<'PY'
"""Retry helpers."""


def parse_retry_after(value):
    return int(value)
PY

git add .gitignore src/retry.py
git commit -q -m 'retry(feat) Add retry-after parsing'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git checkout -q -b feature/log-retries
cat >>src/retry.py <<'PY'


def log_retry(log, value):
    log.info("recieved retry-after %s", value)
PY
git add src/retry.py
git commit -q -m 'retry(feat) Log retry-after values'
git push -q -u origin feature/log-retries
