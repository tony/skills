---
name: case-study-internal
description: "Use when writing a tier-2 internal case study from a business-value run: tagged outcomes, lessons, and a replication guide for other teams."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
disable-model-invocation: true
---

# Internal Case Study (tier 2)

Turn a run package into a narrative case study for internal
circulation: what happened, what it measured, what other teams can
take from it. The tier-2 contract is in `audiences.md`.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/audiences.md`: the tier-2 contract.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report. When the request names a
workflow, take the first line of `runs --workflow <slug>` as the run.

### 2. Ask for what the run package lacks

The run package holds no maintainer, no lessons, and no replication
notes, and may hold no build time. With a question tool, ask the user
once, in one batch (`AskUserQuestion`), for: the maintainer's role, the
build time if `build-hours` is not registered, what worked and what did
not, and what the team would change. Record the answers in
`findings.md` under a `## User-supplied context` heading, with a
build time also appended to `assumptions.yaml` as an ESTIMATED entry
(`provenance.md`); then run `business.py gate <run>` again. Name a
person only as a role. Without a question tool, or without an answer, write
each such part as unknown with the data that would resolve it.

### 3. Render the case study

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

Take every item from the run package or the user's answers; a part
neither holds is written as unknown with the data that would resolve
it, never supplied from inference.

Write it per `../../references/prose-rules.md`.

Then scan for individuals with `../../scripts/business.py scan --run <run>
--tier 2 <run>/reports/case-study-internal.md` (absolute path); it reads the README
`People:` line and reports each name; rewrite it as a role, since tier 2
allows roles only. Then run steps 4 and 5 of `interim-format.md` § Rendering
a report: the money check, then `stamp`.

## Output

Hero success form: `✓ Case study: <one-line outcome with tag>`.
Sections and stopped-run shape as in `interim-format.md`. Panel options: write the public
case study next (read `../case-study-public/SKILL.md` and follow it),
adjust the narrative, or stop.
