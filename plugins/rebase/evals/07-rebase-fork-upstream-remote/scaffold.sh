#!/usr/bin/env bash
# A fork: the branch tracks origin (the fork, whose trunk is stale) while
# upstream carries the real trunk, one commit ahead. The rebase must target
# upstream/main, and the printed push must name the tracked branch
# (origin/feat-evaluate), not the local name.
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
git add .gitignore src/parser.py
git commit -q -m 'parser(feat) Add the tokenizer'

git init --bare -b main ../upstream.git >/dev/null
git remote add upstream ../upstream.git
git push -q upstream main
git clone -q --bare ../upstream.git ../origin.git
git remote add origin ../origin.git
git fetch -q origin
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git symbolic-ref refs/remotes/upstream/HEAD refs/remotes/upstream/main

git switch -q -c evaluate
cat >>src/parser.py <<'PY'


def evaluate(text):
    return sum(int(t) for t in tokenize(text) if t.isdigit())
PY
git add src/parser.py
git commit -q -m 'parser(feat[evaluate]) Sum the numeric tokens'
git push -q origin evaluate:feat-evaluate
git branch -q --set-upstream-to=origin/feat-evaluate evaluate

git switch -q main
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/parser.py")
p.write_text(p.read_text().replace(
    'TOKENS = ("+", "-")\n',
    'import re\n\nTOKENS = ("+", "-", "*", "/")\n\nWHITESPACE = re.compile(r"\\s+")\n'))
PY
git add src/parser.py
git commit -q -m 'parser(feat[tokens]) Recognise multiplicative operators'
git push -q upstream main
git reset -q --hard origin/main
git switch -q evaluate
