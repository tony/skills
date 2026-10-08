#!/usr/bin/env bash
# A trunk plus a feature branch whose diff has one real defect to report.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name eval

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
cat >src/payments.py <<'PY'
"""Charge a customer."""


def charge(client, amount):
    return client.post("/charge", {"amount": amount})
PY
git add -A
git commit -q -m 'feat(payments) Add charge'

git checkout -q -b retry-charges
cat >src/payments.py <<'PY'
"""Charge a customer, retrying on failure."""

import time


def charge(client, amount):
    while True:
        try:
            return client.post("/charge", {"amount": amount})
        except Exception:
            time.sleep(1)
PY
git add -A
git commit -q -m 'feat(payments) Retry failed charges'
