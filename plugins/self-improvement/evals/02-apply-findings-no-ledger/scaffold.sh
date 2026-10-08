#!/usr/bin/env bash
# A catalog repository with one commit and no sweep ledger.
set -euo pipefail

if [ -e .git ]; then
  echo "refusing: the working directory is already a git checkout" >&2
  exit 1
fi

mkdir -p catalog/tidy
cat >catalog/tidy/SKILL.md <<'MD'
---
name: tidy
description: "Use when tidying files."
---

# Tidy

Remove stray files.
MD

git init -q -b main
git config user.email eval@example.invalid
git config user.name eval
git add catalog
git commit -q -m "Add tidy skill"
