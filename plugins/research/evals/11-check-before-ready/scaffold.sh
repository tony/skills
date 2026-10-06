#!/usr/bin/env bash
# Today's run has a finished-looking report whose only source's capture was
# edited after it was recorded, so a fresh check fails.
set -euo pipefail

day=$(date +%F)
run="out/$day/research/vendor-y"
mkdir -p "$run/references/raw"

cat >capture.md <<'MD'
# Vendor Y release notes

Version 4.2 adds a read-only replica mode. Replicas lag the primary by up to
five seconds under normal load.
MD
sha=$(sha256sum capture.md | cut -d' ' -f1)
raw="raw/vendor-y-notes-${sha:0:8}.md"
mv capture.md "$run/references/$raw"
printf '\nReplicas lag the primary by up to thirty seconds under heavy load.\n' \
  >>"$run/references/$raw"

printf '{"added": "%s", "author": "Vendor Y", "capture": "file", "card": "S1-vendor-y-notes.md", "carried_from": null, "file": "%s", "id": "S1", "kind": "vendor", "quotes": ["Replicas lag the primary by up to five seconds"], "ref": "4.2", "replaces": null, "retrieved": "%sT09:00:00Z", "sha256": "%s", "title": "Vendor Y release notes", "url": "https://vendor-y.example/notes/4.2"}\n' \
  "$day" "$raw" "$day" "$sha" >"$run/references/sources.jsonl"

cat >"$run/references/S1-vendor-y-notes.md" <<'MD'
---
id: S1
title: Vendor Y release notes
---

# Vendor Y release notes

Replica lag figure.
MD

cat >"$run/index.md" <<MD
---
namespace: research
topic: vendor-y
subject: Vendor Y replicas
mode: research
audience: private
date: $day
prior: null
---

# Vendor Y replicas

## Question

Can Vendor Y replicas serve reads for the dashboard?

## Log

- $day: opened
MD

cat >"$run/report.md" <<'MD'
# Vendor Y replicas can serve dashboard reads within five seconds of the primary

## Summary

Replicas lag the primary by at most five seconds under normal load, so they can serve the dashboard. Confidence is medium.

## Findings

### Replica lag stays under five seconds under normal load

Replicas lag the primary by up to five seconds under normal load [S1].

Confidence: medium, the vendor's own release notes are the only source.

## Sources

MD
