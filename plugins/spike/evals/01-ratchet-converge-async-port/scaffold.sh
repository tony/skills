#!/usr/bin/env bash
# A repository with no commits and the retry-queue module untracked, so a
# ratchet has code to port but no history to spike against.
set -euo pipefail

git init -b main >/dev/null
mkdir -p src
cat >src/retry_queue.py <<'PY'
"""Callback-style retry queue."""


def enqueue(job, on_done, retries=3):
    try:
        on_done(job())
    except Exception:
        if retries:
            enqueue(job, on_done, retries - 1)
PY
