#!/usr/bin/env bash
# Trunk already carries a vague TODO; the feature branch adds a second one in
# a new file. Only the branch-added TODO is Tier A under a scan.
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

Format commit messages as `type(scope) concise description`.
MD

mkdir -p src
cat >src/queue.py <<'PY'
"""Work queue."""


class Queue:
    def __init__(self) -> None:
        self._items: list[str] = []

    def push(self, item: str) -> None:
        # TODO: revisit this later
        self._items.append(item)
PY

git add .gitignore AGENTS.md src/queue.py
git commit -q -m 'queue(feat) Add the work queue'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feature/queue-drain

cat >src/drain.py <<'PY'
"""Drain helper."""


def drain(items: list[str]) -> list[str]:
    # TODO: figure out later
    return list(items)
PY
git add src/drain.py
git commit -q -m 'queue(feat) Add drain helper'
