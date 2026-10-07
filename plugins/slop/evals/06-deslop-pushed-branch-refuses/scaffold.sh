#!/usr/bin/env bash
# A clean feature branch with a slop commit already pushed to its upstream, so
# a history rewrite would need a force-push.
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
git commit -q -m "$(cat <<'MSG'
notes(feat) Add a comprehensive note

Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
MSG
)"

git push -q -u origin feature/notes
