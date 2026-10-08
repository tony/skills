#!/usr/bin/env bash
# A run whose public case study still carries a ticket ID, so the firewall sweep fails.
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
Names: Acme Corp, Atlas team
MD

cat >"$run/reports/case-study-public.md" <<'MD'
# Tightening drafts with an AI skill

## Context

A mid-size engineering team that tightens written drafts weekly.

## Results

Median per-instance saving 18 min per task, gross (DIRECTIONAL,
MEASURED, n=3 tasks, 13-week window). The largest saving came from
ticket PROJ-482.

## Limitations

Three timed tasks, one team, no counterfactual beyond a manual baseline;
verification time was not measured.
MD
