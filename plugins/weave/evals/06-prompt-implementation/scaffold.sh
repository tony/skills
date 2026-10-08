#!/usr/bin/env bash
# A small committed repository, so commands that need a baseline commit can run.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name eval

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.eval-state
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

printf '# sandbox project\n' >README.md
git add .gitignore README.md
git commit -q -m 'docs(readme) Add the readme'

mkdir -p .eval-state
cp "$(dirname "$0")/../checkout_state.py" .eval-state/check_checkout.py
python3 .eval-state/check_checkout.py capture
