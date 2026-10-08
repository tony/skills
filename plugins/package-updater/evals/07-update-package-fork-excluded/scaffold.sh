#!/usr/bin/env bash
# One repository that is a fork: origin is the user's copy, upstream is the
# project it was forked from; just is pinned in .tool-versions.
set -euo pipefail

git init -q -b main widgets
cd widgets

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

echo 'just 1.36.0' >.tool-versions
git add .gitignore .tool-versions
git -c user.name='Dana Example' \
    -c user.email='dana@example.com' \
    commit -q -m 'chore: pin just'

git remote add origin https://github.com/dana-example/widgets.git
git remote add upstream https://github.com/example-org/widgets.git
