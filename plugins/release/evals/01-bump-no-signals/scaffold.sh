#!/usr/bin/env bash
# A repo with no manifest version, no tags, and no changelog: nothing to
# establish a current version from.
set -euo pipefail

git init -q -b main
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
echo '# demo' >README.md
git add .gitignore README.md
git -c user.email=dev@example.com -c user.name=Dev commit -q -m 'Initial import'
