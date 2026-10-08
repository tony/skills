#!/usr/bin/env bash
# Builds a project whose Vue toolbar has one fixed-width button among content-sized peers.
set -euo pipefail

mkdir -p src/components
cat >src/components/Toolbar.vue <<'VUE'
<template>
  <div class="flex items-center gap-2">
    <button class="h-8 px-2">Save</button>
    <button class="h-8 px-2">Share</button>
    <button class="h-8 w-24 px-2">Theme</button>
  </div>
</template>
VUE
echo '{"dependencies":{"tailwindcss":"^4.0.0"}}' >package.json

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
