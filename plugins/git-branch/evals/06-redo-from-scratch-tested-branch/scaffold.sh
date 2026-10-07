#!/usr/bin/env bash
# A feature branch whose hand-rolled slugify has a unittest suite, so the
# redo has a spec to copy into a worktree and a test command to gate on.
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

printf '# Project\n\nTests: `python3 -m unittest`\n' >README.md
printf 'Run the tests with `python3 -m unittest`. Commit subjects look like `scope(type) Subject`.\n' >AGENTS.md
git add .gitignore README.md AGENTS.md
git commit -q -m 'docs(readme) Add the project readme'

git checkout -q -b feature/slugify
cat >slugify.py <<'PY'
def slugify(text):
    out = ""
    prev_dash = True
    for ch in text:
        if ch.isalnum():
            out += ch.lower()
            prev_dash = False
        elif not prev_dash:
            out += "-"
            prev_dash = True
    if out.endswith("-"):
        out = out[:-1]
    return out
PY
git add slugify.py
git commit -q -m 'slugify(feat) Add slugify'

cat >test_slugify.py <<'PY'
import unittest

from slugify import slugify


class SlugifyTest(unittest.TestCase):
    def test_lowercases_and_joins_words(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_punctuation_runs(self):
        self.assertEqual(slugify("a -- b!!"), "a-b")

    def test_trims_edges(self):
        self.assertEqual(slugify("  Edge  "), "edge")

    def test_empty(self):
        self.assertEqual(slugify(""), "")


if __name__ == "__main__":
    unittest.main()
PY
git add test_slugify.py
git commit -q -m 'slugify(test) Cover slugify'
