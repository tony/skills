#!/usr/bin/env bash
# Two earlier parser goals and their objective under ./Documents.
set -euo pipefail

git init -q -b main
git config user.name eval
git config user.email eval@example.com
printf '.claude/\nDocuments/\n' >.gitignore
cat >parser.py <<'PY'
def parse(text):
    return text.split(",")
PY
mkdir -p tests
cat >tests/test_parser.py <<'PY'
from parser import parse


def test_strips_spaces():
    assert parse("a, b") == ["a", "b"]
PY
git add .gitignore parser.py tests/test_parser.py
git commit -q -m 'Add the comma parser'
git switch -q -c fix-parser

home="$(cd .. && pwd)"
for config in "$home/.config" "${XDG_CONFIG_HOME:-$home/.config}"; do
  mkdir -p "$config/goal-planner"
  printf -- '---\ndocuments: %s/Documents\n---\n' "$PWD" >"$config/goal-planner/profile.md"
done

mkdir -p Documents/2026-10-18/goals Documents/2026-10-18/objectives Documents/2026-10-20/goals
cat >Documents/2026-10-18/objectives/parser-001.md <<'MD'
---
topic: parser
kind: objective
number: 1
host: claude
status: draft
---
# Fix the comma parser

## Tasks

- P1: strip spaces around each field; acceptance: tests/test_parser.py passes.
- P2: add a regression test for empty fields; acceptance: the test fails before the fix.
- P3: document the accepted input in the README; acceptance: the README states it.
MD
cat >Documents/2026-10-18/goals/parser-001.md <<'MD'
---
topic: parser
kind: goal
number: 1
host: claude
status: set
objective: 2026-10-18/objectives/parser-001.md
---
/goal Fix the comma parser per objective parser-001 (tasks P1-P3). Done when each task prints PASS with its commit.
MD
cat >Documents/2026-10-20/goals/parser-002.md <<'MD'
---
topic: parser
kind: goal
number: 2
host: claude
status: set
parent: 2026-10-18/goals/parser-001.md
objective: 2026-10-18/objectives/parser-001.md
---
/goal Finish P2 and P3 from objective parser-001; P1 landed. Keep the tokenizer's public API unchanged while fixing the parser. Done when P2 and P3 print PASS with their commits.
MD
