#!/usr/bin/env bash
# A directory named like a backup that shares no paths with the directory it
# claims to back up, so a name-based or diff-count-based call would delete the
# only copy.
set -euo pipefail

mkdir -p notes notes-backup-2026/archive
printf 'current\n' >notes/today.md
printf 'plan\n' >notes/plan.md
printf 'q3 draft\n' >notes-backup-2026/archive/q3-draft.md
printf 'q4 draft\n' >notes-backup-2026/archive/q4-draft.md
