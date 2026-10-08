#!/usr/bin/env bash
# An empty git repository, so git commands resolve here and not to a parent repo.
set -euo pipefail

git init -q -b main .
git config user.email dev@example.com
git config user.name Dev
git commit -q --allow-empty -m 'Initial commit'
