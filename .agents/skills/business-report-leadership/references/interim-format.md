# Interim Run-Directory Format

## Contents

- Where runs live
- Layout
- Locating an existing run
- Completeness gate
- Rendering a report

The package the `business-research` skill writes and every report command
reads. Commands resolve run locations and verify completeness by
this file.

Script paths in this plugin's files (`references/business.py`)
resolve relative to the file that names them; run the script by its
absolute location.

## Where runs live

`<root>/<YYYY-MM-DD>/business/<workflow>/`, where the date is today's
local date (`date +%F`) and `<workflow>` is the measured skill or
workflow as a kebab-case slug (`lean-tighten`, `pr-review`). The same
slug on different dates is one workflow.

Root: the user's choice, else `~/Documents`; on WSL, the Windows user's
`/mnt/c/Users/<user>/Documents`. These are defaults, not decisions:
always ask the user where to write before creating a run. Running
non-interactively: use the default root and record that decision in the
run README. Nothing is written to disk before the user confirms the
root.

## Layout

```
<run>/
├── index.md
├── README.md
├── sources.md
├── assumptions.yaml
├── raw/
├── measurements/
├── findings.md
└── reports/
```

### index.md

Written when the run is opened: frontmatter with `namespace`
(`business`), `topic` (the workflow slug), and `date`, which lets a
later session find this run and its predecessors. The run's scope and
window live in `README.md`.

### README.md

Scope (what is measured and why), the pinned window (explicit start
and end dates, plus any excluded novelty-ramp window), the
instrument inventory with each instrument marked available or
unavailable, and environment versions for the tools used to collect.

### sources.md

The source manifest: one entry per collected artifact, each with a
stable name (for example `gh-pr-cycle-times`) so figures can cite
it. Every entry records:

- the query or command, verbatim;
- the timestamp of execution;
- the tool version;
- the output file it produced under `raw/`.

### assumptions.yaml

A list of entries:

```yaml
- id: adoption-rate
  description: Fraction of eligible engineers actively using the skill
  value: 0.6
  unit: ratio
  source_type: MEASURED
  confidence: medium
  rationale: Seat admin export, share of eligible seats active weekly
  source_ref: sources.md#seat-admin-export
  retrieved: <YYYY-MM-DD>
  owner: eng-productivity lead
  updated: <YYYY-MM-DD>
```

`source_type` is one of MEASURED | DERIVED | BENCHMARKED |
ESTIMATED; `confidence` is high | medium | low. Every field above is
required on every entry; `references/business.py assumptions <file>`
checks that and the two enumerations. A MEASURED entry's `source_ref`
names a `sources.md` entry; an assumption with no instrument behind
it is ESTIMATED.

### raw/

Immutable snapshots of instrument output, written before anything is
derived from them. Never mutated after write — corrections happen by
adding a new snapshot, never by editing an old one.

### measurements/

Per-topic tables (timing, cycle times, rework, adoption, ...).
Every figure tagged MEASURED, DERIVED, BENCHMARKED, or ESTIMATED, denominator stated.

### findings.md

Synthesis across measurements. Every figure tagged. Unknowns listed
explicitly, each with "what data would resolve this".

### reports/

Created empty by the `business-research` skill; written only by the report
commands: `leadership.md`, `org-wide.md`, `case-study-internal.md`,
`case-study-public.md`, `pr-release.md`. A report command finding it
absent creates it rather than failing.

## Locating an existing run

Precedence: an explicit path argument, else the newest run of the
named workflow, else the newest business run. List runs newest
first, ordered by the date in the path:

```console
$ references/business.py runs
```

It searches `~/Documents` and, on WSL, the Windows users' Documents
folders; `--root <dir>` adds one. Confirm the chosen run with the
user before rendering anything from it. Running non-interactively:
proceed with the newest run and say which one in the output's Run
section instead of asking.

## Completeness gate

Report commands refuse to render from an incomplete package. Check,
in order:

1. `README.md` exists and states a pinned window.
2. `sources.md` exists and every entry carries a verbatim query,
   timestamp, tool version, and output file.
3. `assumptions.yaml` passes `references/business.py assumptions`.
4. Every figure in `measurements/` and `findings.md` carries one of
   the four provenance tags, and every MEASURED figure's citation
   resolves: collect the cited manifest names and verify each names
   an entry that exists in `sources.md` — a mechanical check, not a
   judgment call.
5. Every unknown in `findings.md` states what data would resolve it.

On any failure: do not render, and treat it as a stopped run (see
Rendering a report).

## Rendering a report

Every report skill follows this frame. The skill names its own tier,
references, and body.

Value is engineer-hours, cycle time, and capacity, never money.

1. Locate the run: the `$ARGUMENTS` path if given, else per "Locating
   an existing run".
2. Run the completeness gate. Load the skill's other references only
   after it passes.
3. Render the body, then write the report to `<run>/reports/<name>.md`.

### Finished run

Open with one hero line: the skill's success form, or `✓ Evidence
report: <supported claim, unknowns named>` when the package holds no
committable figure (early instrumentation, open unknowns). Then these sections,
with any the skill adds:

1. `## Run`: the run chosen and its pinned window.
2. `## Gate`: the completeness result.
3. `## Report`: where it was written and the headline.

End with an `ask-user-choice` panel offering the skill's next steps.
Skip it in plan mode or when running non-interactively, where the
output ends after `## Report`.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
✓ Leadership report: 310 engineer-hours per quarter saved (DERIVED)

## Run

- 2026-07-14/business/review-skill, window 2026-04-01..2026-06-30.

## Gate

- Passed: sources, assumptions, tags, and unknowns complete.

## Report

- Written to reports/leadership.md.
- Strongest limitation: review latency covers 41 PRs, one team.
```

### Stopped run

A run that halts (run not found, gate failed, missing input, failed
sweep) is one hero line `⚠ Refused: <reason in one sentence>`, then
one short paragraph or list of what the user must do next. No `Run`,
`Gate`, or `Report` sections, no panel. State only what happened:
never claim a check failed that did not run, and never describe
references that were not loaded.

```text
⚠ Refused: sources.md has an entry with no output file.

Add the missing snapshot or remove the entry, then render again.
```

### Paths and commits

Name a run as `<date>/business/<workflow>` relative to its root.
Print an absolute or temporary path only when the user must act on
that file.

Steps that ask the user (`ask-user-choice`) state their
non-interactive default; an explicit authorization in the request
covers only the action named.
