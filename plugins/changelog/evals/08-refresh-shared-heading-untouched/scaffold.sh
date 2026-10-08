#!/usr/bin/env bash
# Trunk and branch both have entries under the shared "### Fixes" heading; the
# branch entry is accurate, so only the heading rename is left to refuse.
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

### Fixes

- Restore the config loader's search path so project files win over defaults (#12)

## 1.4.0 (2026-07-02)

### Features

- Add the retry queue (#8)
MD

mkdir -p src
printf 'MAX_BACKOFF_SECONDS = 60.0\n' >src/retry.py

git add .gitignore AGENTS.md CHANGES.md src/retry.py
git commit -q -m 'retry(feat) Add the backoff calculation'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c fix/retry-cap

printf 'MAX_BACKOFF_SECONDS = 30.0\n' >src/retry.py
python3 - <<'PY'
import pathlib
p = pathlib.Path("CHANGES.md")
p.write_text(
    p.read_text().replace(
        "(#12)\n",
        "(#12)\n- Cap the retry backoff at 30 seconds instead of 60 (#31)\n",
        1,
    )
)
PY
git add CHANGES.md src/retry.py
git commit -q -m 'retry(fix) Cap the backoff at 30 seconds'
