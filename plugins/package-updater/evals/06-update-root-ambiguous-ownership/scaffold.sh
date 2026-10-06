#!/usr/bin/env bash
# One repository under the sweep root: organisation remote, trunk history
# authored only by a bot, an outdated toolchain pin.
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

echo 'uv 0.7.8' >.tool-versions
git add .gitignore .tool-versions
git -c user.name='dependabot[bot]' \
    -c user.email='49699333+dependabot[bot]@users.noreply.github.com' \
    commit -q -m 'chore(deps) Bump uv'

git remote add origin https://github.com/example-org/widgets.git
