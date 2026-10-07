---
name: case-study-internal
description: Write the tier-2 internal case study — situation, what was built, tagged outcomes with denominators, lessons, replication guide for other teams
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
user-invocable: true
disable-model-invocation: true
---

# Internal Case Study (tier 2)

Turn a run package into a narrative case study for internal
circulation: what happened, what it measured, what other teams can
take from it. Tier 2: internal team and repo names allowed;
individuals anonymized to roles.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/audiences.md`: the tier-2 contract.

User arguments: $ARGUMENTS

Paths under `../../scripts/` resolve from this skill's directory: print the absolute path once and write it literally in each command, since shell variables do not persist between Bash calls.

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Render the case study

Write `<run>/reports/case-study-internal.md` as a narrative in this
fixed order:

1. Situation: the team, the recurring task, why it cost enough
   to act on.
2. What was built: the skill or workflow, its build time
   (tagged), and who maintains it.
3. Measured outcomes: every figure tagged, denominator stated,
   window pinned. Include the costs: verification time, failed
   runs, maintenance.
4. Lessons: what worked, what did not, what the team would do
   differently.
5. How other teams can replicate: prerequisites, the expected
   ramp (and the excluded novelty window), and where results are
   likely to differ.

Anonymize individuals to roles. Team and repo names stay.

Write it per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ Case study: <one-line outcome with tag>`.
Sections and stopped-run shape as in `interim-format.md`. Panel options: write the public
case study next (read `../case-study-public/SKILL.md` and follow it),
adjust the narrative, or stop.
