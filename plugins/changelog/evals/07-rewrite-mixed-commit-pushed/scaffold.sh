#!/usr/bin/env bash
# A pushed branch with one changelog-only commit and one commit that mixes code
# with a changelog entry, so the rewrite can drop the first but not the second.
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

### Features

### Fixes

- Restore the config loader's search path so project files win over defaults (#12)
- Keep the retry queue from dropping jobs on shutdown (#13)
- Stop the scheduler logging every tick at info level (#14)

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

python3 - <<'PY'
import pathlib
p = pathlib.Path("CHANGES.md")
p.write_text(p.read_text().replace("### Features\n", "### Features\n\n- first draft of the ping entry (#2)\n"))
PY
git add CHANGES.md
git commit -q -m 'docs(CHANGES) First draft of the ping entry'

printf 'def ping() -> str:\n    return "PONG"\n' >src/ping.py
python3 - <<'PY'
import pathlib
p = pathlib.Path("CHANGES.md")
p.write_text(
    p.read_text().replace(
        "info level (#14)\n",
        "info level (#14)\n- Make the ping reply uppercase (#2)\n",
    )
)
PY
git add CHANGES.md src/ping.py
git commit -q -m 'ping(feat) Shout the reply'

git push -q -u origin feat/ping-loud
