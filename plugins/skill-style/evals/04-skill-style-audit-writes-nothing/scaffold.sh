#!/usr/bin/env bash
# A tracked skill with a filler intro, so an audit has something to report.
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
mkdir -p skills/tidy
cat >skills/tidy/SKILL.md <<'MD'
---
name: tidy
description: "Use when tidying imports in a Python file."
allowed-tools: ["Bash", "Edit"]
---

# Tidy imports

Imports are an important part of any Python program, and keeping them
tidy is considered a best practice.

## Sort the imports

Sort the imports of the named file with the project's formatter.
MD
git add .gitignore skills
git commit -q -m 'skills(feat) Add tidy'
