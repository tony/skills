#!/usr/bin/env bash
# An assessment run whose only source for its deciding criterion is the vendor's own page.
set -euo pipefail

day=2026-01-15
run="out/$day/research/vendor-z"
mkdir -p "$run/references/raw" "$run/data"

cat >capture.md <<'MD'
# Vendor Z Queue

Vendor Z Queue sustains 1 million messages per second on a three-node cluster.
MD
sha=$(sha256sum capture.md | cut -d' ' -f1)
raw="raw/vendor-z-queue-${sha:0:8}.md"
mv capture.md "$run/references/$raw"

printf '{"added": "%s", "author": "Vendor Z", "capture": "file", "card": "S1-vendor-z-queue.md", "carried_from": null, "file": "%s", "id": "S1", "kind": "vendor", "quotes": ["sustains 1 million messages per second"], "ref": "2.0", "replaces": null, "retrieved": "%sT09:00:00Z", "sha256": "%s", "title": "Vendor Z Queue", "url": "https://vendor-z.example/queue/2.0"}\n' \
  "$day" "$raw" "$day" "$sha" >"$run/references/sources.jsonl"

cat >"$run/references/S1-vendor-z-queue.md" <<'MD'
---
id: S1
title: Vendor Z Queue
---

# Vendor Z Queue

Vendor's throughput claim.
MD

cat >"$run/index.md" <<MD
---
namespace: research
topic: vendor-z
subject: Adopt Vendor Z Queue
mode: assessment
audience: private
date: $day
prior: null
---

# Adopt Vendor Z Queue

## Question

- Decision: adopt Vendor Z Queue, trial it, or hold?

## Criteria

| Criterion | Strong | Weak |
|-----------|--------|------|
| Throughput | Above 500k messages per second | Below 50k |

## Log

- $day: opened
MD
printf '%s\n' "- $(date +%F): opened" >>"$run/index.md"
