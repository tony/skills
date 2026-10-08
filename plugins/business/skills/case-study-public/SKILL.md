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
kind, aggregates and ranges only, every headline claim triangulated.

Read `../../references/interim-format.md` first. It defines the run
location, the completeness gate, and the output frame. Defer these
until the gate passes:

- `../../references/provenance.md`
- `../../references/evidence.md`: the external evidence table and the
  triangulation procedure. Re-verify the sources you cite first.
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

Apply the triangulation procedure from `evidence.md` to each
headline claim. A claim outside the defensible external range is
removed or kept only with an explicit methodology defense. Record
each outcome.

### 4. Final checklist pass

Run the tier-3 final checklist from `audiences.md` over the finished
draft, item by item, including the scanner. Fix every hit, then write
`<run>/reports/case-study-public.md`.

Write it per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ Public case study: <headline with tag>`.
Sections and stopped-run shape as in `interim-format.md`, with `## Sanitization` between
`## Gate` and `## Report`: the checklist results item by item and the
triangulation outcome per headline claim. Panel options: derive the PR
release next (read `../pr-release/SKILL.md` and follow it), tighten a
claim, or stop.
