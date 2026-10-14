---
name: case-study-public
description: "Use when writing a tier-3 public case study from a business-value run: sanitized, triangulated against external evidence, with limitations."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion", "WebFetch"]
argument-hint: "[run directory]"
disable-model-invocation: true
---

# Public Case Study (tier 3)

Turn a run package into a case study fit for external publication.
Tier 3 is the hard sanitization tier: no internal identifiers of any
kind, aggregates and ranges only, every headline claim placed against
external evidence or marked as having none.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/measurement.md`: statistics discipline and the
  counterfactual quality ladder; use its rung definitions verbatim.
- `../../references/evidence.md`: the external evidence table, its
  re-verify step, and the triangulation procedure.
- `../../references/audiences.md`: the tier-3 contract and the final
  checklist.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run and pass the gate

Per `interim-format.md` § Rendering a report.

### 2. Draft under the tier-3 contract

Draft in this order, sanitized from the first word, not afterwards:

1. Context: the kind of team and the kind of task, described
   without identifying anyone or anything internal.
2. Approach: what was built, in transferable terms.
3. Results: aggregates and ranges only; every figure tagged as
   tag plus method phrase per `audiences.md`; denominators and
   pinned-window lengths stated; honest rounding.
4. Limitations: candid and mandatory: measurement weaknesses,
   the counterfactual rung, what was not measured.

### 3. Triangulate every headline claim

Apply the triangulation procedure from `evidence.md` to each headline
claim. Where a source measures the same outcome and the claim is far
from it, remove the claim or keep it with an explicit methodology
defense. Where none does, as for PR cycle time and review latency, write
"no external comparator" and keep the counterfactual rung and the
limitation. Record each outcome.

### 4. Write, scan, and stamp

Write the draft per `../../references/prose-rules.md` to
`<run>/reports/case-study-public.md`. Run the tier-3 final checklist from
`audiences.md` over that saved file, item by item, starting with
`scan --run <run>`; rewrite the file and scan it again until the scan
prints `clean`. Then run `stamp` (`interim-format.md` § Rendering a
report, step 5).

## Output

Hero success form: `✓ Public case study: <headline with tag>`.
Sections and stopped-run shape as in `interim-format.md`, with `## Run`
in its tier-3 form and `## Sanitization` between `## Gate` and
`## Report`: the checklist results item by item and the external
placement per headline claim, sanitized and scanned under the tier-3
reply contract in `audiences.md`. Panel options: derive the PR
release next (read `../pr-release/SKILL.md` and follow it), tighten a
claim, or stop.
