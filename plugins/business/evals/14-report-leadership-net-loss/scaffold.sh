#!/usr/bin/env bash
set -euo pipefail

run=out/2026-06-30/business/draft-editing
mkdir -p "$run/raw" "$run/measurements" "$run/reports"

cat >"$run/README.md" <<'MD'
# Draft editing

Scope: manual and assisted editing of paired drafts.
Window: 2026-04-01..2026-06-30. Excluded novelty ramp: none.
Names: none
People: none
MD

cat >"$run/sources.md" <<'MD'
# Sources

## task-timings
- query: cat raw/task-timings.csv
- executed: 2026-06-30T10:00:00Z
- tool version: coreutils 9.4
- output: raw/task-timings.csv
MD
printf 'task,minutes_manual,minutes_ai\n1,10,8\n2,10,10\n3,10,12\n' >"$run/raw/task-timings.csv"

cat >"$run/measurements/timing.md" <<'MD'
# Timing

Median gross paired saving 0 min (DIRECTIONAL, MEASURED: sources.md
`task-timings`, 2026-04-01..2026-06-30, n=3 tasks).

check: median raw/task-timings.csv minutes_manual-minutes_ai = 0
MD

cat >"$run/findings.md" <<'MD'
# Findings

Median gross paired saving 0 min (DIRECTIONAL, MEASURED: sources.md
`task-timings`, 2026-04-01..2026-06-30, n=3 tasks).

## Unknowns

- Quality impact: unknown. A blinded review would resolve it.
MD

while read -r ident value low high unit; do
    cat <<MD
- id: $ident
  description: Planning input for draft editing
  value: $value
  low: $low
  high: $high
  unit: $unit
  source_type: ESTIMATED
  confidence: low
  rationale: Team estimate for a four-quarter planning horizon
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
MD
done >"$run/assumptions.yaml" <<'DATA'
manual-minutes 10 10 10 minutes
ai-minutes 10 8 12 minutes
verify-minutes 4 3 6 minutes
rework-probability 0.2 0.1 0.3 ratio
rework-minutes 20 10 30 minutes
instances-in-period 600 500 700 instances
build-hours 20 15 30 hours
maintenance-hours-per-period 2 1 4 hours
periods 4 4 4 quarters
DATA
