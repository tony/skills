#!/usr/bin/env bash
# A run whose report cites S1 for a claim S1's capture never makes.
set -euo pipefail

run=out/2026-01-15/research/vendor-y
mkdir -p "$run/references/raw"
cat >capture.md <<'MD'
# Vendor Y release notes

Version 4.2 adds a read-only replica mode. Replicas lag the primary by up to
five seconds under normal load.
MD
sha=$(sha256sum capture.md | cut -d' ' -f1)
raw="raw/vendor-y-notes-${sha:0:8}.md"
mv capture.md "$run/references/$raw"

cat >"$run/index.md" <<'MD'
---
namespace: research
topic: vendor-y
subject: Vendor Y replicas
mode: research
audience: private
date: 2026-01-15
prior: null
---

# Vendor Y replicas

## Question

Can Vendor Y replicas serve reads for the dashboard?

## Log

- 2026-01-15: opened
MD

printf '{"added": "2026-01-15", "author": "Vendor Y", "capture": "file", "card": "S1-vendor-y-notes.md", "carried_from": null, "file": "%s", "id": "S1", "kind": "vendor", "quotes": ["Replicas lag the primary by up to five seconds"], "ref": "4.2", "replaces": null, "retrieved": "2026-01-15T09:00:00Z", "sha256": "%s", "title": "Vendor Y release notes", "url": "https://vendor-y.example/notes/4.2"}\n' "$raw" "$sha" >"$run/references/sources.jsonl"

cat >"$run/references/S1-vendor-y-notes.md" <<'MD'
---
id: S1
title: Vendor Y release notes
---

# Vendor Y release notes

Replica lag figure.
MD

cat >"$run/report.md" <<'MD'
# Vendor Y replicas can serve dashboard reads within five seconds of the primary

## Summary

Replicas lag by at most five seconds, and failover to a replica is automatic.

## Findings

### Replica lag stays under five seconds under normal load

Replicas lag the primary by up to five seconds [S1].

### Failover to a replica happens automatically within a minute

Vendor Y promotes a replica automatically when the primary fails [S1].

## Sources

- S1
MD
