#!/usr/bin/env bash
# NOTES.md holds verbose prose that tighten would cut.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

cat >NOTES.md <<'MD'
# Cache notes

It is important to note that the cache is, in essence, a comprehensive and
robust layer that basically leverages an in-memory map in order to make
lookups faster for the vast majority of callers at this point in time.

Entries expire after 60 seconds because the upstream API rate-limits us.
MD
git add -A
git commit -qm "Add cache notes"
