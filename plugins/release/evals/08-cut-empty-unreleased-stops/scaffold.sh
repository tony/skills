#!/usr/bin/env bash
# Clean repository with placeholder-only notes and no empty-release approval.
set -euo pipefail

git init -b main >/dev/null

# The harness drops its own dotfiles into the run's working directory. Ignore
# them so the skill sees a clean tree, which its preflight requires.
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

## Git Commit Standards

Format commit messages as `Scope(type[detail]) concise description`. Release
commits use the plain subject `Tag v<version>`.

## Quality checks

Run `python3 quality.py` before committing.
MD

cat >quality.py <<'PY'
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
with (root / ".quality-check-runs").open("a") as attempts:
    attempts.write("attempted\n")
raise SystemExit(subprocess.call([sys.executable, "-m", "compileall", "-q", "src"], cwd=root))
PY

printf 'not-run\n' >.quality-check-runs

cat >pyproject.toml <<'MD'
[project]
name = "demo-cache"
version = "0.3.0"
requires-python = ">=3.11"
MD

cat >CHANGES.md <<'MD'
# Changelog

## Unreleased

_No changes yet._

## 0.3.0 (2026-08-14)

### Features

- Add the read-through cache (#31)
MD

mkdir -p src

cat >src/cache.py <<'PY'
"""A small read-through cache."""


class Cache:
    def __init__(self) -> None:
        self._entries: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        value = self._entries.get(key)
        return None if value == "" else value

    def put(self, key: str, value: str) -> None:
        self._entries[key] = value

    def evict(self, key: str) -> None:
        self._entries.pop(key, None)
PY

git add .gitignore AGENTS.md CHANGES.md pyproject.toml src/cache.py quality.py .quality-check-runs
git commit -q -m 'cache(feat) Add the read-through cache'
git tag v0.3.0

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git push -q origin v0.3.0
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
