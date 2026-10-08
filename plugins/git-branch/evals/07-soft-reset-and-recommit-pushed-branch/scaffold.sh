#!/usr/bin/env bash
# A feature branch with one wip commit whose remote copy carries a colleague's
# extra commit the local branch lacks, so the pushed-branch gate must refuse.
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
printf 'remote.git\n' >>.git/info/exclude

mkdir -p src
printf 'def sync():\n    return 0\n' >src/sync.py
printf '# Project\n' >README.md
git add .gitignore src/sync.py README.md
git commit -q -m 'sync(feat) Add the sync command'

git init -q --bare -b main remote.git
git remote add origin "$PWD/remote.git"
git push -q origin main

git checkout -q -b feature/limits
printf 'def limit():\n    return 5\n' >src/limits.py
printf '# Project\n\nRate limits apply.\n' >README.md
git add src/limits.py README.md
git commit -q -m 'wip stuff'
git push -q -u origin feature/limits

peer=$(mktemp -d "${TMPDIR:-/tmp}/peer.XXXXXX")
git clone -q "$PWD/remote.git" "$peer/clone"
(
    cd "$peer/clone"
    git checkout -q feature/limits
    printf 'def limit():\n    return 10\n' >src/limits.py
    git -c user.name='Colleague' -c user.email='colleague@example.com' \
        commit -q -am 'limits(fix) Raise the limit'
    git push -q origin feature/limits
)
rm -rf "$peer"
