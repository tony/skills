#!/usr/bin/env bash
# One earlier run of the topic, written the way topic.py writes it.
set -euo pipefail

run=out/2026-01-08/research/sqlite-wal
mkdir -p "$run/references/raw"
cat >caps.md <<'MD'
# Write-Ahead Logging

WAL provides more concurrency as readers do not block writers and a writer
does not block readers.
MD
sha=$(sha256sum caps.md | cut -d' ' -f1)
raw="raw/write-ahead-logging-${sha:0:8}.md"
mv caps.md "$run/references/$raw"

cat >"$run/index.md" <<'MD'
---
namespace: research
topic: sqlite-wal
subject: SQLite WAL
mode: research
audience: private
date: 2026-01-08
prior: null
---

# SQLite WAL

## Question

When do readers and writers block each other in WAL mode?

## Scope

- In: SQLite 3.46 WAL documentation
- Out: the rollback journal

## Open questions

- [ ] Does WAL work over a network filesystem?

## Log

- 2026-01-08: opened
MD

printf '{"added": "2026-01-08", "author": "SQLite", "capture": "file", "card": "S1-write-ahead-logging.md", "carried_from": null, "file": "%s", "id": "S1", "quotes": ["readers do not block writers"], "ref": "3.46.0", "replaces": null, "retrieved": "2026-01-08T10:00:00Z", "sha256": "%s", "title": "Write-Ahead Logging", "url": "https://sqlite.org/wal.html"}\n' "$raw" "$sha" >"$run/references/sources.jsonl"

cat >"$run/references/S1-write-ahead-logging.md" <<MD
---
id: S1
title: Write-Ahead Logging
url: https://sqlite.org/wal.html
---

# Write-Ahead Logging

Supports the readers-never-block claim.
MD

cat >"$run/report.md" <<'MD'
# WAL lets readers and the writer run at once

## Summary

Readers and the single writer do not block each other in WAL mode.

## Findings

### Readers never wait for the writer

The WAL documentation says readers do not block writers [S1].

## Sources

- S1
MD
