#!/usr/bin/env bash
# A two-skill catalog and a history in which one skill's runs repeat a paste.
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
GIT_AUTHOR_DATE="2026-01-01T12:00:00Z" GIT_COMMITTER_DATE="2026-01-01T12:00:00Z" \
  git commit -q -m "Add demo skills"

python3 - <<'PY'
import json
from datetime import datetime, timezone

start = datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp() * 1000
with open("history.jsonl", "w", encoding="utf-8") as fh:
    for i in range(12):
        tail = " and only touch *.log files" if i < 8 else ""
        rec = {
            "display": f"/demo:used run {i}{tail}",
            "timestamp": int(start + i * 86400000),
            "project": f"/work/proj{i % 3}",
        }
        fh.write(json.dumps(rec) + "\n")
PY
