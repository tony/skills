#!/usr/bin/env bash
# A repo whose AGENTS.md names a check script and a commit format, so a landed
# commit can be checked for format and for tool trailers.
set -euo pipefail

git init -b main >/dev/null

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
MD

cat >AGENTS.md <<'MD'
# Conventions

Run the checks before every commit:

    sh check.sh

Commit subjects use the form `Scope(type) summary`, for example
`sync(feat) Add the sync command`.
MD

cat >check.sh <<'SH'
#!/bin/sh
python3 -m unittest discover -s tests
SH

mkdir -p src tests
cat >src/sync.py <<'PY'
"""Sync command."""


def sync(source, destination):
    copied = 0
    for item in source.list():
        destination.write(item)
        copied += 1
    return copied
PY

touch src/__init__.py
cat >tests/test_sync.py <<'PY'
import unittest

from src.sync import sync


class Box:
    def __init__(self, items):
        self.items = list(items)

    def list(self):
        return self.items

    def write(self, item):
        self.items.append(item)


class SyncTest(unittest.TestCase):
    def test_copies_every_item(self):
        self.assertEqual(sync(Box([1, 2]), Box([])), 2)


if __name__ == "__main__":
    unittest.main()
PY

git add .gitignore AGENTS.md check.sh src tests
git commit -q -m 'sync(feat) Add the sync command'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
