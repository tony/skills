#!/usr/bin/env bash
# main holds one fat comment; the topic branch adds another in the same file.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

cat >cache.py <<'PY'
def get(store, key):
    # This function looks up the key in the store and returns the value
    return store.get(key)
PY
git add -A
git commit -qm "Add cache lookup"

git checkout -qb topic
cat >>cache.py <<'PY'


def put(store, key, value):
    # This function puts the value in the store under the key
    store[key] = value
PY
git commit -qam "Add cache put"
