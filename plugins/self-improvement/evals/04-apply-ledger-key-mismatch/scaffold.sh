#!/usr/bin/env bash
# A catalog repo plus a ledger whose key was computed for a different HEAD.
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

git init -q
git config user.email eval@example.invalid
git config user.name eval
git add catalog
git commit -q -m "Add tidy skill"

python3 - <<'PY'
import hashlib
import json

head = "1" * 40
findings = [
    {
        "id": "f1",
        "verdict": "absent",
        "expected_change": "pastes of the file-type filter drop below 2 per 30 days",
        "skill": "tidy",
    }
]
text = head + "\n" + "".join(f"{f['id']}\t{f['verdict']}\n" for f in findings)
ledger = {
    "version": 1,
    "created": "2026-01-01",
    "resweep_on": "2026-02-01",
    "head": head,
    "key": hashlib.sha256(text.encode()).hexdigest(),
    "findings": findings,
}
with open("ledger.json", "w", encoding="utf-8") as fh:
    json.dump(ledger, fh, indent=2)
PY
