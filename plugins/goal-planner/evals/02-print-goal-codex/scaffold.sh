#!/usr/bin/env bash
# A parser repository on a fix branch and a profile keeping goals under ./Documents.
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
if [ -n "${HOME:-}" ] && [ "$HOME" != "$home" ]; then
  echo "refusing: run inside an eval sandbox, whose HOME is this directory's parent" >&2
  exit 1
fi
mkdir -p "$home/.config/goal-planner"
printf -- '---\ndocuments: %s/Documents\n---\n' "$PWD" >"$home/.config/goal-planner/profile.md"
