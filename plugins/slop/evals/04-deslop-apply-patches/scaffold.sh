#!/usr/bin/env bash
# A local-only feature branch whose second commit adds a vague TODO, the one
# Tier A diff finding. Asking to apply patches must land a fixup commit.
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

Format commit messages as `Scope(type[detail]) concise description`.
MD

mkdir -p src
cat >src/queue.py <<'PY'
"""Work queue."""


class Queue:
    def __init__(self) -> None:
        self._items: list[str] = []
PY

git add .gitignore AGENTS.md src/queue.py
git commit -q -m 'queue(feat) Add the work queue'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feature/queue-push

cat >>src/queue.py <<'PY'

    def push(self, item: str) -> None:
        # TODO: revisit this later
        self._items.append(item)
PY
git add src/queue.py
git commit -q -m 'queue(feat) Add push'
