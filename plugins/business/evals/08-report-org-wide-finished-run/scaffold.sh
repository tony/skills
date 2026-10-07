#!/usr/bin/env bash
# A complete, gate-passing run whose register holds every org-wide projection input.
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

Scope: time to tighten a draft, measured per task.
Window: 2026-04-01..2026-06-30. Excluded novelty ramp: none.
Names: none
Instruments: git available, gh unavailable.
Timezone: UTC. Tools: git 2.43.
MD

cat >"$run/sources.md" <<'MD'
# Sources

## task-timings
- query: cat raw/task-timings.csv
- executed: 2026-06-30T10:00:00Z
- tool version: coreutils 9.4
- output: raw/task-timings.csv
MD
printf 'task,minutes_manual,minutes_ai\n1,30,12\n2,25,14\n3,40,18\n' >"$run/raw/task-timings.csv"

cat >"$run/measurements/timing.md" <<'MD'
# Timing

Median per-instance saving 18 min (DIRECTIONAL, MEASURED: sources.md
`task-timings`, 2026-04-01..2026-06-30, n=3 tasks).

check: median raw/task-timings.csv minutes_manual-minutes_ai = 18
MD

cat >"$run/findings.md" <<'MD'
# Findings

Median per-instance saving 18 min (DIRECTIONAL, MEASURED: sources.md
`task-timings`, 2026-04-01..2026-06-30, n=3 tasks).

## Unknowns

- Verification time: unknown. A per-task review log would resolve it.
MD

cat >"$run/assumptions.yaml" <<'MD'
- id: addressable-population
  description: Engineers whose work includes tightening drafts
  value: 40
  low: 30
  high: 50
  unit: engineers
  source_type: ESTIMATED
  confidence: low
  rationale: Team roster count, not an activity export
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
- id: instances-per-person-year
  description: Drafts each engineer tightens per year
  value: 100
  low: 100
  high: 100
  unit: instances
  source_type: ESTIMATED
  confidence: low
  rationale: Team lead's recollection of weekly volume
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
- id: baseline-minutes
  description: Manual minutes to tighten one draft
  value: 30
  low: 25
  high: 40
  unit: minutes
  source_type: MEASURED
  confidence: low
  rationale: Median manual time in the three timed tasks
  source_ref: sources.md#task-timings
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
- id: savings-rate
  description: Share of manual time saved, net of review
  value: 0.4
  low: 0.3
  high: 0.6
  unit: ratio
  source_type: ESTIMATED
  confidence: low
  rationale: 18 of 30 minutes gross, cut for unmeasured review time
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
- id: adoption-rate
  description: Share of addressable engineers who use the skill weekly
  value: 0.5
  low: 0.3
  high: 0.7
  unit: ratio
  source_type: ESTIMATED
  confidence: low
  rationale: Team lead's recollection, no usage export
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
- id: realization-rate
  description: Share of saved time that becomes usable capacity
  value: 0.6
  low: 0.4
  high: 0.8
  unit: ratio
  source_type: ESTIMATED
  confidence: low
  rationale: Saved minutes are scattered across the week
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
MD
