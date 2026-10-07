#!/usr/bin/env bash
# A branch whose code makes one review claim wrong, one improbable, and one true.
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
printf '"""Report helpers."""\n' >src/report.py
git add .gitignore src/report.py
git commit -q -m 'report(feat) Add module'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git checkout -q -b feature/report
cat >src/report.py <<'PY'
"""Report helpers."""

import os


def read_values(path):
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return [float(line) for line in handle if line.strip()]


def average(values):
    return sum(values) / len(values)


def summary(path):
    return average(read_values(path))


def label(name):
    return "report:" + name


def title():
    return label("weekly")
PY
git add src/report.py
git commit -q -m 'report(feat) Add summary and labels'
