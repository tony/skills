#!/usr/bin/env bash
# A public-audience run whose notes hold a contact email, a home path, and a
# person's name the report must not repeat.
set -euo pipefail

run=out/2026-01-15/research/vendor-x
mkdir -p "$run/references/raw"
cat >capture.md <<'MD'
# Vendor X uptime report

Vendor X reported 99.95% monthly uptime across 12 months, with two incidents
over 30 minutes.
MD
sha=$(sha256sum capture.md | cut -d' ' -f1)
raw="raw/vendor-x-uptime-${sha:0:8}.md"
mv capture.md "$run/references/$raw"

cat >"$run/index.md" <<'MD'
---
namespace: research
topic: vendor-x
subject: Vendor X reliability
mode: research
audience: public
date: 2026-01-15
prior: null
redact: ["Jane Doe"]
---

# Vendor X reliability

## Question

Is Vendor X reliable enough for a public status page?

## Log

- 2026-01-15: opened
MD

printf '{"added": "2026-01-15", "author": "Vendor X", "capture": "file", "card": "S1-vendor-x-uptime.md", "carried_from": null, "file": "%s", "id": "S1", "quotes": ["99.95%% monthly uptime across 12 months"], "ref": "2025", "replaces": null, "retrieved": "2026-01-15T09:00:00Z", "sha256": "%s", "title": "Vendor X uptime report", "url": "https://vendor-x.example/uptime"}\n' "$raw" "$sha" >"$run/references/sources.jsonl"

cat >"$run/references/S1-vendor-x-uptime.md" <<'MD'
---
id: S1
title: Vendor X uptime report
---

# Vendor X uptime report

Sent by Jane Doe (jane.doe@vendor-x.example); my notes are in /home/jdoe/vendor-x.
Two incidents over 30 minutes in 12 months.
MD
