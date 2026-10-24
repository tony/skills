#!/usr/bin/env bash
# A small repository to run a command in.
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
