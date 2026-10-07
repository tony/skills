#!/usr/bin/env bash
# A feature branch with a changelog-only commit and an uncommitted code edit,
# so the dirty-tree precondition must stop the rewrite.
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
Changelog entries land under `## Unreleased` in `CHANGES.md`.
MD

cat >CHANGES.md <<'MD'
# Changelog

## Unreleased

## 1.0.0 (2026-07-02)

- Initial release
MD

mkdir -p src
printf 'def ping() -> str:\n    return "pong"\n' >src/ping.py
git add .gitignore AGENTS.md CHANGES.md src/ping.py
git commit -q -m 'ping(feat) Add ping'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/ping-loud

printf 'def ping() -> str:\n    return "PONG"\n' >src/ping.py
git add src/ping.py
git commit -q -m 'ping(feat) Shout the reply'

python3 - <<'PY'
import pathlib
p = pathlib.Path("CHANGES.md")
p.write_text(p.read_text().replace("## Unreleased\n", "## Unreleased\n\n- first draft of the ping entry (#2)\n"))
PY
git add CHANGES.md
git commit -q -m 'docs(CHANGES) First draft of the ping entry'

printf "# scratch\n" >notes.txt
printf "wip\n" >>src/ping.py
