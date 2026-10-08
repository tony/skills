#!/usr/bin/env bash
# A two-skill catalog and a prompt-history fixture that invokes only one skill.
set -euo pipefail

if [ -e .git ]; then
  echo "refusing: the working directory is already a git checkout" >&2
  exit 1
fi

base=plugins
for name in used idle; do
  mkdir -p "$base/demo/skills/$name"
  cat >"$base/demo/skills/$name/SKILL.md" <<MD
---
name: $name
description: "Use when running the $name demo."
---

# $name

Do the $name demo.
MD
done

git init -q -b main
git config user.email eval@example.invalid
git config user.name eval
git add "$base"
git commit -q -m "Add demo skills"

python3 - <<'PY'
import json

with open("history.jsonl", "w", encoding="utf-8") as fh:
    for i in range(12):
        rec = {
            "display": f"/demo:used run {i}",
            "timestamp": 1790000000000 + i * 86400000,
            "project": f"/work/proj{i % 3}",
        }
        fh.write(json.dumps(rec) + "\n")
PY
