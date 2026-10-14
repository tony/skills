---
name: report-org-wide
description: "Use when rendering the tier-1 org-wide projection from a business-value run: adoption, realization, scenarios, and sensitivity ranking."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
disable-model-invocation: true
---

# Org-Wide Report (tier 1)

Project a measured per-instance saving across the organization and
close with a summary the whole company can read. The tier-1 contract is
in `audiences.md`.

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
go to step 3. A negative savings rate is valid: it is a measured loss,
reported in step 3, and you never ask for a replacement value.

For each id it names, ask the user once via `AskUserQuestion`, in one
batch, explaining each factor per `measurement.md`. Append every
answer to `assumptions.yaml` as a full entry (`interim-format.md` §
assumptions.yaml; ESTIMATED, or MEASURED when an instrument export
gives it), with optional `low` and `high` fields bounding the
scenarios, then run `project` again. A disagreement it prints between
`savings-rate` and its parts is corrected in the entry you appended,
never in a MEASURED entry. Never proceed with a default of 1.0 for
adoption or realization. Without a question tool, or without an answer,
halt per `interim-format.md` § Stopped run. Name each missing input
once, in plain words, in the hero line; list the register ids only in
the next-step sentence.

### 3. Render the report

Copy projection, scenario, segment, and sensitivity totals from `project`;
copy factor values, bounds, and tags from the assumptions register. Never
calculate those totals by hand. Write `<run>/reports/org-wide.md` with this fixed
structure:

1. Bottom-up build: the full chain
   `Annual_hours_saved = V * F * t * s * a * r`, every factor shown
   with its own tag; the population segmented addressable ⊃ served ⊃
   realized, all three reported.
2. Scenarios: conservative, base, upside as `measurement.md` defines
   them, with the differing inputs listed per scenario.
3. Sensitivity: the script's one-way ranking, largest swing first.
4. What has to be true: break-even framing: the values the
   inputs must reach for the projection to hold, taken from registered
   bounds.
   Under a loss, the values at which the savings rate would turn
   positive.
5. Plain-language summary: for the whole company: no
   methodology jargon, no formula notation; figures still tagged and
   true.

The projection is gross of build and maintenance upkeep; say so in the
plain-language summary.

Loss branch: when `project` prints a negative figure or a `net loss`
line, keep each printed sign in the hero and the scenarios. The
plain-language summary says that measured time per task went up, reports
the hours as printed, and does not soften it or propose a different
savings rate. A registered net savings rate includes its assumed
review allowance; distinguish that estimate from observed review timing.
The summary introduces no new figures or before/after medians: use the tagged
measurements already reported, without turning a time gap into a causal claim.
If any measurement is per-person, roll it up to the team before it
appears here.

Write it per `../../references/prose-rules.md`.

Then run steps 4 and 5 of `interim-format.md` § Rendering a report: the
money check, then `stamp`.

## Output

Hero success form: `✓ Org-wide projection: <conservative figure>,
upside <figure> (<tag>)`. Sections and stopped-run shape as in `interim-format.md`; `## Gate` also gives the
adoption and realization values used with their register ids, and `## Report` names
the most sensitive input. Panel options: write an internal case study
next (read `../case-study-internal/SKILL.md` and follow it), revisit
an assumption, or stop.
