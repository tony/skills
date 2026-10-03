# Interim Run-Directory Format

The package the `business-research` skill writes and every report command
reads. Commands resolve run locations and verify completeness by
this file.

## Where runs live

`<root>/<YYYY-MM-DD>/business/<workflow>/`: the research plugin's
topic layout, with namespace `business` and the measured skill or
workflow as the topic (`lean-tighten`, `pr-review`).

Open the run with the `research:foray` skill, passing
`--namespace business` and the workflow as the topic. It picks the
root (Documents; on WSL the Windows user's Documents), writes the
run's `index.md`, and lists earlier runs of the same workflow.
Without the research plugin, use `~/Documents`, or on WSL
`/mnt/c/Users/<user>/Documents`.

These roots are defaults, not decisions — always ask the user where
to write before creating a run. Running non-interactively: use the
default root and record that decision in the run README.

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

Written when the run is opened: the topic's frontmatter (namespace,
workflow, date) that lets `research:foray` find this run and its
predecessors. The run's scope and window live in `README.md`.

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
  source_type: ESTIMATED
  confidence: medium
  rationale: Seat admin export shows 60% weekly active in June
  source_ref: sources.md#gh-user-activity
  retrieved: 2026-07-24
  owner: eng-productivity lead
  updated: 2026-07-24
```

`source_type` is one of MEASURED | DERIVED | BENCHMARKED |
ESTIMATED; `confidence` is high | medium | low. Every field above is
required on every entry.

### raw/

Immutable snapshots of instrument output, written before anything is
derived from them. Never mutated after write — corrections happen by
adding a new snapshot, never by editing an old one.

### measurements/

Per-topic tables (timing, cycle times, rework, adoption, ...).
Every figure tagged per `provenance.md`, denominator stated.

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
first:

```console
$ sh -c 'ls -dt "$HOME"/Documents/*/business/*/ /mnt/c/Users/*/Documents/*/business/*/ 2>/dev/null' | head -5
```

Runs written before workflow topics sit directly in
`<date>/business/`; pass their path explicitly.

Confirm the chosen run with the user before rendering anything from
it. Running non-interactively: proceed with the newest run and record
the choice in the output's Run section instead of asking.

## Completeness gate

Report commands refuse to render from an incomplete package. Check,
in order:

1. `README.md` exists and states a pinned window.
2. `sources.md` exists and every entry carries a verbatim query,
   timestamp, tool version, and output file.
3. `assumptions.yaml` parses and every entry has every required
   field.
4. Every figure in `measurements/` and `findings.md` carries one of
   the four provenance tags, and every MEASURED figure's citation
   resolves: collect the cited manifest names and verify each names
   an entry that exists in `sources.md` — a mechanical check, not a
   judgment call.
5. Every unknown in `findings.md` states what data would resolve it.

On any failure: do not render. List exactly what is missing and
point at the `business-research` skill to fill the gaps.
