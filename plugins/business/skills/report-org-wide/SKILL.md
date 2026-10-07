---
name: report-org-wide
description: Render the tier-1 org-wide projection — explicit adoption and realization inputs, scenario spread, sensitivity ranking, plain-language company close
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
user-invocable: true
disable-model-invocation: true
---

# Org-Wide Report (tier 1)

Project a measured per-instance saving across the organization and
close with a summary the whole company can read. Tier 1: team-level
aggregates only, no individual names anywhere.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/measurement.md`: the projection chain, the
  population segments, and the multiplier rule.
- `../../references/audiences.md`: the tier-1 contract.

User arguments: $ARGUMENTS

Paths under `../../scripts/` resolve from this skill's directory: print the absolute path once and write it literally in each command, since shell variables do not persist between Bash calls.

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Secure the multipliers

Read adoption (`adoption-rate`) and realization (`realization-rate`)
from `assumptions.yaml`. If either is absent, ask the user via `AskUserQuestion`, explaining what
each means per `measurement.md`, and append the answer to the register
with rationale and owner (ESTIMATED, or MEASURED when an instrument
export gives it). Never proceed with a default of 1.0. Without a
question tool, or without an answer, halt with `⚠ Refused: <factor>
missing from the assumptions register` and tell the user to add it
(`/business:research` or editing `assumptions.yaml`).

### 3. Render the report

Run `../../scripts/business.py project <run>` and take every figure
in sections 1 to 3 from its output; never do that arithmetic by hand.
It exits 1 and names each missing or out-of-range register id, which
is a stopped run. Write `<run>/reports/org-wide.md` with this fixed
structure:

1. Bottom-up build: the full chain
   `Annual_hours_saved = V * F * t * s * a * r`, every factor shown
   with its own tag; the population segmented addressable ⊃ served ⊃
   realized, all three reported.
2. Scenarios: conservative, base, upside as `measurement.md` defines
   them, with the differing inputs listed per scenario.
3. Sensitivity: the script's one-way ranking, largest swing first.
4. What has to be true: break-even framing: the values the
   inputs must reach for the projection to hold.
5. Plain-language summary: for the whole company: no
   methodology jargon, no formula notation; figures still tagged and
   true.

Team-level aggregates only. If any measurement is per-person, roll
it up before it appears here.

Write it per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ Org-wide projection: <conservative figure with
tag>`. Sections and stopped-run shape as in `interim-format.md`; `## Gate` also gives the
adoption and realization values used with their register ids, and `## Report` names
the most sensitive input. Panel options: write an internal case study
next (read `../case-study-internal/SKILL.md` and follow it), revisit
an assumption, or stop.
