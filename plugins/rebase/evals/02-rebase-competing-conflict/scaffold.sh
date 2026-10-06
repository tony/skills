#!/usr/bin/env bash
# A feature branch and trunk that set the same line to competing values, so
# the rebase conflicts and the right resolution is a product decision.
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

mkdir -p src
cat >src/parser.py <<'PY'
"""Expression parser."""

TOKENS = ("+", "-")


def tokenize(text):
    return [t for t in text.split() if t]
PY

git add .gitignore src/parser.py
git commit -q -m 'parser(feat) Add the tokenizer'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feature/strict
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/parser.py")
p.write_text(p.read_text().replace(
    "return [t for t in text.split() if t]",
    "return [t for t in text.split() if t in TOKENS or t.isdigit()]"))
PY
git add src/parser.py
git commit -q -m 'parser(fix[tokenize]) Drop unknown tokens'

git switch -q main
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/parser.py")
p.write_text(p.read_text().replace(
    "return [t for t in text.split() if t]",
    "return [t for t in text.split() if t] or [\"\"]"))
PY
git add src/parser.py
git commit -q -m 'parser(fix[tokenize]) Return an empty token for blank input'
git push -q origin main
git switch -q feature/strict
