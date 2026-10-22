#!/usr/bin/env bash
# A repository with an uncommitted edit to a tracked file.
set -euo pipefail

git init -q -b main
git config user.name eval
git config user.email eval@example.com
printf '# Notes\n' >notes.md
printf 'test:\n\t@true\n' >Makefile
git add .
git commit -q -m 'chore(repo) start'
printf '# Notes\n\nA draft paragraph.\n' >notes.md
