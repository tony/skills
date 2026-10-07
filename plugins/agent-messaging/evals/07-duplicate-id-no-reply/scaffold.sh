#!/usr/bin/env bash
# Builds an empty project; the case carries its message in the prompt.
set -euo pipefail

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
