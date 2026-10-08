---
name: report-leadership
description: "Use when rendering a tier-0 leadership report from a completed business-value run, with SCQA and a conservative value case."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
user-invocable: true
disable-model-invocation: true
---

# Leadership Report (tier 0)

Render the full-detail leadership report from a run package. Tier 0
withholds nothing: names, raw links, registers inline.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/measurement.md`: the value build, break-even,
  guardrails, the counterfactual ladder.
- `../../references/evidence.md`: external context for the
  pre-answered objections. Re-verify the sources you cite first. Without a
  fetch tool, ask the user to confirm each figure you cite; do not narrate the missing tool.
- `../../references/audiences.md`: the tier-0 contract.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Compute the figures

Run `../../scripts/business.py breakeven <run>` (absolute path) and
`../../scripts/business.py stats` for intervals (n<5 prints a range, never a "95% interval"). Every computed
figure in the report (`S_inst`, `S_net`, `N_breakeven`, and the
conservative, base, and upside scenarios) comes from that output,
copied as printed; never compute, round, or convert one yourself.
The `conservative` lines are the committed figures. Each `missing:`
line is an unknown naming that register id, with the data that would
resolve it. Printed problem lines are a register error: fix the
register first. Exit 1 with `missing:` lines only means nothing is
computable: render an evidence report per `measurement.md`, with the
measured medians only and break-even stated as unknown.

### 3. Render the report

Write `<run>/reports/leadership.md` with this fixed structure:

1. SCQA opening: Situation, Complication, Question, Answer,
   with the Answer stated first.
2. Exhibits: every exhibit title is a full-sentence takeaway; one
   message per exhibit; a source, query, and date-range note under
   each.
3. Value build: every multiplier explicit, per the chains in
   `measurement.md`; break-even from the script output, or stated unknown.
4. Scenarios: the conservative scenario (defined in `measurement.md`)
   is the committed number; base and upside appear as context, never
   as the headline.
5. Assumptions register and data dictionary: appendix, inline
   from `assumptions.yaml` plus definitions of every metric used.
6. Known limitations: each with a confidence label.
7. What would flip this conclusion: the input thresholds at
   which the answer changes.
8. Pre-answered objections: at minimum: how do you know the
   skill caused this (name the counterfactual rung); does the
   savings rate survive the verification tax; who maintains the
   skill.

Write it per `../../references/prose-rules.md`.

Then run the money check, step 4 of `interim-format.md` § Rendering a report.

## Output

Hero success form: `✓ Leadership report: <committed figure with
tag>`. Sections and stopped-run shape as in `interim-format.md`; `## Report` also names the
strongest limitation. Panel options: render the org-wide projection
next (read `../report-org-wide/SKILL.md` and follow it), adjust
assumptions and re-render, or stop.
