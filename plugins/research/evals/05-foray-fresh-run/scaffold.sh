#!/usr/bin/env bash
# A saved capture, so the run can record a source without network access.
set -euo pipefail

mkdir -p caps
cat >caps/wal.md <<'MD'
# Write-Ahead Logging

WAL provides more concurrency as readers do not block writers and a writer
does not block readers. Reading and writing can proceed concurrently.

A checkpoint moves the WAL file transactions back into the database.
MD
