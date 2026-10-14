#!/usr/bin/env bash
# A run with measurements but no public case study to derive a release from.
set -euo pipefail

run=out/2026-06-30/business/lean-tighten
mkdir -p "$run/raw" "$run/measurements" "$run/reports"

cat >"$run/index.md" <<'MD'
---
namespace: business
topic: lean-tighten
date: 2026-06-30
---
MD

cat >"$run/README.md" <<'MD'
# lean-tighten

Window: 2026-04-01..2026-06-30.
Names: none
People: none
MD

cat >"$run/measurements/timing.md" <<'MD'
# Timing

Median per-instance saving 18 min (DIRECTIONAL, MEASURED: sources.md
`task-timings`, 2026-04-01..2026-06-30, n=3 tasks).
MD
