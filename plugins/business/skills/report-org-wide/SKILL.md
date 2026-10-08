---
name: report-org-wide
description: "Use when rendering the tier-1 org-wide projection from a business-value run: adoption, realization, scenarios, and sensitivity ranking."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
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

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Secure the inputs

Run `../../scripts/business.py project <run>` with its absolute path.
It prints every register id the projection needs that is missing or
out of range (all six factors in the chain below, not only adoption
and realization) and exits 1. Exit 0 means every input is present;
go to step 3.

For each id it names, ask the user once via `AskUserQuestion`, in one
batch, explaining each factor per `measurement.md`. Append every
answer to `assumptions.yaml` with rationale and owner (ESTIMATED, or
MEASURED when an instrument export gives it), optional `low` and
`high` fields bounding the scenarios, then run `project` again. Never
proceed with a default of 1.0 for adoption or realization. Without a
question tool, or without an answer, halt per `interim-format.md` §
Stopped run. Name each missing input once, in plain words, in the hero
line; list the register ids only in the next-step sentence.

### 3. Render the report

Take every figure in sections 1 to 3 from the `project` output of
step 2; never do that arithmetic by hand. Write `<run>/reports/org-wide.md` with this fixed
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

The projection is gross of build and maintenance upkeep; say so in the
plain-language summary. Team-level aggregates only. If any measurement is per-person, roll
it up before it appears here.

Write it per `../../references/prose-rules.md`.

Then run the money check, step 4 of `interim-format.md` § Rendering a report.

## Output

Hero success form: `✓ Org-wide projection: <conservative figure with
tag>`. Sections and stopped-run shape as in `interim-format.md`; `## Gate` also gives the
adoption and realization values used with their register ids, and `## Report` names
the most sensitive input. Panel options: write an internal case study
next (read `../case-study-internal/SKILL.md` and follow it), revisit
an assumption, or stop.
