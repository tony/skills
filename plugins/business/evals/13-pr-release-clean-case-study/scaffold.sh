#!/usr/bin/env bash
set -euo pipefail

run=out/2026-06-30/business/lean-tighten
mkdir -p "$run/reports"

cat >"$run/README.md" <<'MD'
# lean-tighten

Window: 2026-04-01..2026-06-30.
Names: Acme, Atlas

Internal forecast: 9999 hours. Never a public-case-study input.
MD

cat >"$run/reports/case-study-public.md" <<'MD'
# Draft tightening: a directional gross saving

## Context

A writing workflow in a product team, observed during the second quarter.

## Results

The median paired saving was 18 minutes per task, gross (DIRECTIONAL,
MEASURED from paired timings, n=3 tasks, 13-week window). The observed
paired savings ranged from 11 to 22 minutes per task (DIRECTIONAL,
MEASURED from the same 3 tasks over the same 13-week window).

## Limitations

The sample is small and uses a manual baseline, not randomized assignment.
Review time was not measured. These gross paired gaps do not establish a
causal effect or organization-wide realized capacity.
MD

printf 'User-owned draft: keep this file unchanged.\n' >"$run/reports/.reply-check.md"

python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../scripts" && pwd)/business.py" stamp "$run" "$run/reports/case-study-public.md" >/dev/null
