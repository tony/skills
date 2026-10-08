#!/usr/bin/env bash
# A directory that is a fresh repository with no commits and no skill catalog.
set -euo pipefail

if [ -e .git ]; then
  echo "refusing: the working directory is already a git checkout" >&2
  exit 1
fi
git init -q
echo "notes" >notes.txt
