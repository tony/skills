#!/usr/bin/env bash
# A finished report on a dated run that passes its ship check offline.
set -euo pipefail

run=out/2026-01-15/research/vendor-y
mkdir -p "$run/references/raw"

cat >"$run/references/raw/vendor-y-release-notes-c6177ab0.md" <<'MD'
# Vendor Y release notes

Version 4.2 adds a read-only replica mode. Replicas lag the primary by up to
five seconds under normal load.
MD

cat >"$run/references/S1-vendor-y-release-notes.md" <<'MD'
---
id: S1
title: Vendor Y release notes
author: Vendor Y
url: "https://docs.vendor-y.io/notes/4.2"
ref: "4.2"
retrieved: "2026-10-07T04:36:01Z"
sha256: c6177ab0eec4fcf71ec1142940aaa8ba1eabcbcda6ce1471fd7d067ea85532dc
file: raw/vendor-y-release-notes-c6177ab0.md
quotes: ["Replicas lag the primary by up to five seconds"]
kind: vendor
---

# Vendor Y release notes

What this source supports, and where.
MD

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

The question this topic answers.

## Scope

- In:
- Out:

## Open questions

- [ ] 

## Log

- 2026-01-15: opened
- 2026-10-06: reviewed 1 cited line in report.md (7548d43d)
MD

cat >"$run/report.md" <<'MD'
# Vendor Y replicas can serve dashboard reads within five seconds of the primary

2026-01-15 · research/vendor-y · research · private

## Summary

Replicas lag the primary by at most five seconds under normal load, so they can serve the dashboard. Confidence is medium.

## Findings

### Replica lag stays under five seconds under normal load

Replicas lag the primary by up to five seconds under normal load [S1]. Confidence: medium, the vendor's own release notes are the only source.

## Open questions

- Does lag grow under heavy writes? A measured test would settle it.

## Method

Read the vendor's 4.2 release notes.

## Sources

| Id | Source | Author | Kind | Ref | Retrieved | Capture | Check |
|---|---|---|---|---|---|---|---|
| S1 | [Vendor Y release notes](https://docs.vendor-y.io/notes/4.2) | Vendor Y | vendor | 4.2 | 2026-10-07 | provided | checked |
MD

cat >"$run/references/sources.jsonl" <<'JSON'
{"added": "2026-01-15", "author": "Vendor Y", "capture": "file", "card": "S1-vendor-y-release-notes.md", "carried_from": null, "file": "raw/vendor-y-release-notes-c6177ab0.md", "id": "S1", "kind": "vendor", "quotes": ["Replicas lag the primary by up to five seconds"], "ref": "4.2", "replaces": null, "response": null, "retrieved": "2026-10-07T04:36:01Z", "sha256": "c6177ab0eec4fcf71ec1142940aaa8ba1eabcbcda6ce1471fd7d067ea85532dc", "title": "Vendor Y release notes", "unretrieved": null, "url": "https://docs.vendor-y.io/notes/4.2"}
JSON
