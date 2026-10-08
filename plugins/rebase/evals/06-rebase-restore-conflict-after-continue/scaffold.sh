#!/usr/bin/env bash
# Replay conflicts mechanically; restoring local notes then conflicts with
# trunk's competing notes.
set -euo pipefail

git init -b main >/dev/null
git config user.name Eval
git config user.email eval@example.invalid

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
printf 'draft notes\n' >notes.txt

git add .gitignore src/parser.py notes.txt
git commit -q -m 'parser(feat) Add the tokenizer'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feature/evaluate
cat >>src/parser.py <<'PY'


def evaluate(text):
    return sum(int(t) for t in tokenize(text) if t.isdigit())
PY
git add src/parser.py
git commit -q -m 'parser(feat[evaluate]) Sum the numeric tokens'

git switch -q main
cat >>src/parser.py <<'PY'


def render(tokens):
    return " ".join(tokens)
PY
printf 'trunk notes\n' >notes.txt
git add src/parser.py notes.txt
git commit -q -m 'parser(feat[render]) Join tokens back into text'
git push -q origin main
git switch -q feature/evaluate

printf 'unsaved edit\n' >notes.txt
