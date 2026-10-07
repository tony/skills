#!/usr/bin/env bash
# A repository with one commit and an unrelated notes file.
set -euo pipefail

if [ -e .git ]; then
  echo "refusing: the working directory is already a git checkout" >&2
  exit 1
fi

git init -q -b main
git config user.email eval@example.invalid
git config user.name eval
echo "notes" >notes.txt
git add notes.txt
git commit -q -m "Add notes"
