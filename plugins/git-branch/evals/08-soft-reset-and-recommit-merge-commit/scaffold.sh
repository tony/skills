#!/usr/bin/env bash
# A feature branch whose range holds a merge commit that carries a side
# branch's work, so the merge-commit gate must refuse the collapse.
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
printf 'def sync():\n    return 0\n' >src/sync.py
printf '# Project\n' >README.md
git add .gitignore src/sync.py README.md
git commit -q -m 'sync(feat) Add the sync command'

git checkout -q -b feature/limits
printf 'def limit():\n    return 5\n' >src/limits.py
git add src/limits.py
git commit -q -m 'wip stuff'

git checkout -q -b side/docs
printf '# Project\n\nRate limits apply.\n' >README.md
git -c user.name='Colleague' -c user.email='colleague@example.com' \
    commit -q -am 'docs(readme) Describe rate limits'

git checkout -q feature/limits
git merge -q --no-ff -m 'Merge side/docs into feature/limits' side/docs
