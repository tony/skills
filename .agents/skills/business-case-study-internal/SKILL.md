---
name: business-case-study-internal
description: >-
  Use when writing a tier-2 internal case study from a business-value run:
  tagged outcomes, lessons, and a replication guide for other teams.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
metadata:
  argument-hint: "[run directory]"
  source: "plugins/business/skills/case-study-internal/SKILL.md"
---

# Internal Case Study (tier 2)

Turn a run package into a narrative case study for internal
circulation: what happened, what it measured, what other teams can
take from it. Tier 2: internal team and repo names allowed;
individuals anonymized to roles.

Read `references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `references/provenance.md`
- `references/audiences.md`: the tier-2 contract.

User arguments: $ARGUMENTS

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

Anonymize individuals to roles. Team and repo names stay. Take every
item from the run package; a part it does not hold (maintainer, build
time, lessons) is written as unknown with the data that would resolve
it, never supplied from inference.

Write it per `references/prose-rules.md`.

Then run the money check, step 4 of `interim-format.md` § Rendering a report.

## Output

Hero success form: `✓ Case study: <one-line outcome with tag>`.
Sections and stopped-run shape as in `interim-format.md`. Panel options: write the public
case study next (read the `business-case-study-public` skill and follow it),
adjust the narrative, or stop.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
