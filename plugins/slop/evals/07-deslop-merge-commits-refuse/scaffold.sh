#!/usr/bin/env bash
# A clean, unpushed feature branch that merged a side branch, so autosquash
# without --rebase-merges would flatten it.
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
printf '# Notes\n' >NOTES.md
git add .gitignore NOTES.md
git commit -q -m 'notes(feat) Add notes'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feature/notes
printf 'A comprehensive, robust and seamless note.\n' >>NOTES.md
git add NOTES.md
git commit -q -m 'notes(feat) Add a comprehensive note'

git switch -q -c side/extra main
printf 'Extra.\n' >EXTRA.md
git add EXTRA.md
git commit -q -m 'notes(feat) Add extras'

git switch -q feature/notes
git merge -q --no-ff -m 'notes(feat) Merge extras' side/extra
