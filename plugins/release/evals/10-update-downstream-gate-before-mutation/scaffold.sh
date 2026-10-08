#!/usr/bin/env bash
# A consumer checkout under work/ with a bare origin. The package is pinned one
# release behind, so the run has something to bump; the gate must hold first.
set -euo pipefail

mkdir -p work origin
git init -q -b main work/app-one
cd work/app-one
git config user.email dev@example.com
git config user.name Dev

cat >AGENTS.md <<'MD'
# Conventions

## Quality checks

Run `python3 -m compileall -q src` before committing.
MD

cat >pyproject.toml <<'MD'
[project]
name = "app-one"
version = "1.0.0"
dependencies = ["six==1.15.0"]
MD

mkdir -p src
echo 'print("ok")' >src/app.py
git add AGENTS.md pyproject.toml src/app.py
git commit -q -m 'app(feat) Initial import'

git init -q --bare -b main ../../origin/app-one.git
git remote add origin ../../origin/app-one.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
