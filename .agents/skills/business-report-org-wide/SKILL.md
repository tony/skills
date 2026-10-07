---
name: business-report-org-wide
description: >-
  Render the tier-1 org-wide projection — explicit adoption and realization
  inputs, scenario spread, sensitivity ranking, plain-language company close
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
metadata:
  argument-hint: "[run directory]"
  source: "plugins/business/skills/report-org-wide/SKILL.md"
---

# Org-Wide Report (tier 1)

Project a measured per-instance saving across the organization and
close with a summary the whole company can read. Tier 1: team-level
aggregates only, no individual names anywhere.

Read `references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `references/provenance.md`
- `references/measurement.md`: the projection chain, the
  population segments, and the multiplier rule.
- `references/audiences.md`: the tier-1 contract.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Secure the multipliers

Read adoption `a` and realization `r` from `assumptions.yaml`. If
either is absent, ask the user via `ask-user-choice`, explaining what
each means per `measurement.md`, and append the answer to the register
with rationale and owner (ESTIMATED, or MEASURED when an instrument
export gives it). Never proceed with a default of 1.0. Without a
question tool, or without an answer, halt with `⚠ Refused: <factor>
missing from the assumptions register` and tell the user to add it
(the `business-research` skill or editing `assumptions.yaml`).

### 3. Render the report

Write `<run>/reports/org-wide.md` with this fixed structure:

1. **Bottom-up build**: the full chain
   `Annual_hours_saved = V * F * t * s * a * r`, every factor shown
   with its own tag; the population segmented addressable ⊃ served ⊃
   realized, all three reported.
2. **Scenarios**: conservative, base, upside, with the differing
   assumptions listed per scenario.
3. **Sensitivity**: one-way ranking: which single input moves the
   outcome most, in order.
4. **What has to be true**: break-even framing: the values the
   inputs must reach for the projection to hold.
5. **Plain-language summary**: for the whole company: no
   methodology jargon, no formula notation; figures still tagged and
   true.

Team-level aggregates only. If any measurement is per-person, roll
it up before it appears here.

Write it per `references/prose-rules.md`.

## Output

Hero success form: `✓ Org-wide projection: <conservative figure with
tag>`. Sections and stopped-run shape as in `interim-format.md`; `## Gate` also gives the
`a` and `r` values used with their register ids, and `## Report` names
the most sensitive input. Panel options: write an internal case study
next (read the `business-case-study-internal` skill and follow it), revisit
an assumption, or stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
