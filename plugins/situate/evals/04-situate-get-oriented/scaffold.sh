#!/usr/bin/env bash
# A published branch with no upstream and no hosted repository identity.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

mkdir -p src
printf 'def greet(name):\n    return "hi " + name\n' >src/greet.py
git add src/greet.py
git commit -q -m 'Add greeting helper'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/shout
printf 'def shout(name):\n    return greet(name).upper()\n' >>src/greet.py
git commit -qam 'Add shout variant'
git push -q origin feat/shout
