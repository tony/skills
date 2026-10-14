# Interim Run-Directory Format

## Contents

- Where runs live
- Layout
- Locating an existing run
- Completeness gate
- Rendering a report

The package `/business:research` writes and every report command
reads. Commands resolve run locations and verify completeness by
this file.

Script paths in this plugin's files climb from the file that names
them to the plugin's `scripts/` directory: one level up from a
reference, two from a skill. Print the absolute path once and write it
literally in each command: shell variables do not persist between Bash
calls.

## Where runs live

`<root>/<YYYY-MM-DD>/business/<workflow>/`, where the date is today's
local date (`date +%F`) and `<workflow>` is the measured skill or
workflow as a kebab-case slug (`lean-tighten`, `pr-review`). The same
slug on different dates is one workflow.

Root: the user's choice, else `~/Documents`; on WSL, the Windows
Documents folder. These are defaults, not decisions: always ask the
user where to write before creating a run, and write nothing before
they confirm the root. Non-interactive: `/business:research` prints its
plan and stops unless the request names the root; the report commands
write only inside the run they were given.

Open a new run with `init` (absolute path to the script; `--date` takes
`YYYY-MM-DD` and defaults to today's local date). It creates `index.md`,
a `README.md` skeleton, `raw/`, `measurements/`, and `reports/`, keeps
any file already there, and prints the run path:

```console
$ ../scripts/business.py init \
    --root <root> \
    <workflow>
```

`init` exits 2 when the workflow is not a kebab-case slug or when `raw/`
of that day's run already holds snapshots. To add data to an existing
run, skip `init` and write new snapshots under new names; otherwise ask
the user for another date.

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
unavailable, environment versions for the tools used to collect, and
a `Names:` line listing every organization, repository, team,
person, and internal workflow or skill name the run touches, comma-separated. Research fills it from
the repositories and teams it queried and the people the user named; `scan --run <run>`
reads it as the deny list. `gate` fails when the line is empty;
write `Names: none` when the run touches no names. The skeleton `init`
writes has an empty `Names:` line, so the gate fails until it is filled.
A `collect-prs` warning that rows lack a column or that reviews were
truncated is recorded here as well as in `sources.md`.

### sources.md

The source manifest: one `## <name>` entry per collected artifact,
named stably (for example `gh-pr-cycle-times`) so figures can cite
it. Every entry has these labeled lines; `executed` is read from the
clock (`date -u +%FT%TZ`) when the query runs, because the gate rejects
anything that is not an ISO timestamp:

```text
- query: the command, verbatim
- executed: 2026-06-30T10:00:00Z
- tool version: gh 2.60.1
- output: raw/pr-cycle-times.json
```

A warning the collector printed goes in the entry as a `- warning:`
line.

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
required on every entry (`provenance.md` says what `source_ref` and
`retrieved` hold for each type), and `low` and `high` are optional.
Write bare `key: value` lines: a `- id:` line at the left margin, its
fields indented two spaces, no quotes, no trailing `# comment`, no
nesting. `../scripts/business.py assumptions <file>` checks the format,
the two enumerations, numeric `value`s, ISO dates, and that one quantity
has one id (`measurement.md` names the ids). A MEASURED entry's
`source_ref` names a `sources.md` entry; an assumption with no
instrument behind it is ESTIMATED. An empty file passes: a run that only
measures registers no assumptions.

### raw/

Immutable snapshots of instrument output, written before anything is
derived from them. Never mutated after write; corrections happen by
adding a new snapshot, never by editing an old one.

Per-person data (logins, per-user adoption) stays out of `raw/` when an
aggregate answers the question; otherwise tell the user the run root
may be cloud-synced and ask how long to keep the snapshots. Non-interactive:
write no per-person data.

### measurements/

Per-topic tables (timing, cycle times, rework, adoption, ...).
Every figure tagged per `provenance.md`, denominator stated.

A MEASURED figure computed from a CSV in `raw/` gets a line the gate
recomputes:

```text
check: median raw/task-timings.csv minutes_manual-minutes_ai = 18
```

The statistic is `median`, `mean`, `min`, `max`, or `n`; the column is
one header or `a-b` for a per-row difference. Rows with a blank cell
in a needed column drop out. `business.py stats --csv <file> --column
<column>` takes the same column syntax for medians and intervals.

### findings.md

Synthesis across measurements. Every figure tagged. Unknowns listed
explicitly, each with "what data would resolve this".

### reports/

Created empty by `/business:research`; written only by the report
commands: `leadership.md`, `org-wide.md`, `case-study-internal.md`,
`case-study-public.md`, `pr-release.md`. A report command finding it
absent creates it rather than failing.

## Locating an existing run

Precedence: an explicit path argument, else the newest run of the
named workflow, else the newest business run. List runs newest
first, ordered by the date in the path:

```console
$ ../scripts/business.py runs
```

It searches only `~/Documents` and, on WSL, the Windows users'
Documents folders, skipping any it cannot read. Pass `--root <dir>`
whenever the run lives under another root, such as the one the user
named; it then searches that directory instead. It never searches the current
directory. Confirm the chosen run with the
user before rendering anything from it. Non-interactive:
proceed with the newest run and say which one in the output's Run
section instead of asking.

## Completeness gate

Report commands refuse to render from an incomplete package. Run:

```console
$ ../scripts/business.py gate <run>
```

It prints each problem and exits 1, or prints `ok`. It checks that
`README.md` states a pinned window and has a `Names:` line (`Names: none` is allowed); that every `sources.md` entry has a
query, an ISO `executed` timestamp, a tool version, and an existing
output file; that `assumptions.yaml` passes `business.py assumptions`
and its MEASURED `source_ref`s resolve; that every figure with a unit
sits in a sentence that carries a tag; that every MEASURED figure cites
an existing `sources.md` entry and, when that entry's output is a CSV,
has a `check:` line over it; that every `check:` line recomputes from
`raw/`; that no currency symbol, code, or money vocabulary (negations
included) appears in `measurements/` or `findings.md`; and that each
bullet under a heading containing "unknown" names the data that would
resolve it (the bullet must contain one of `resolve`, `need`,
`require`, `data`, `export`, and not only to say there is none).

The script cannot judge whether a tag is right or a figure is
missing a unit it does not recognize. Read `measurements/` and
`findings.md` once for those. On any failure: do not render, and
treat it as a stopped run (see Rendering a report).

## Rendering a report

Every report skill follows this frame. The skill names its own tier,
references, and body.

Value is engineer-hours, cycle time, and capacity, never money.

1. Locate the run: the `$ARGUMENTS` path if given, else per "Locating
   an existing run".
2. Run the completeness gate (above). Load the skill's other references only
   after it passes.
3. Render the body, then write the report to `<run>/reports/<name>.md`.
4. Check the saved report for money, with the absolute path to the
   script:

   ```console
   $ ../scripts/business.py scan \
       --rules currency,money-term \
       <run>/reports/<name>.md
   ```

   Reword every hit and rerun until it prints `clean`. Say the report was
   scanned only after this ran.
5. Record what the report was written from; use the absolute path:

   ```console
   $ ../scripts/business.py stamp \
       <run> \
       <name>.md
   ```

   Before rendering from or deriving off an earlier report, run
   `../scripts/business.py fresh <run>`: it prints one line per report
   that is unstamped or whose inputs changed since it was written, or
   `ok`. Only the lines for the reports you rely on matter. A stale case
   study is regenerated by its skill, and a stale release is derived
   again.

### Finished run

Open with one hero line: the skill's success form, or `✓ Evidence
report: <supported claim, unknowns named>` when the package holds no
committable figure (early instrumentation, open unknowns). Then these sections,
with any the skill adds:

1. `## Run`: the run chosen and its pinned window. A tier-3 reply writes
   the task category and rounded window instead (`audiences.md`).
2. `## Gate`: the completeness result.
3. `## Report`: where it was written and the headline.

End with an `AskUserQuestion` panel offering the skill's next steps.
Skip it in plan mode. Where no question tool exists (Codex, headless
runs), print the options as a plain list after `## Report` and stop.

Reply form, owned here: plain text outside any code fence, plain
bullets, no bold labels (never `- **Label:** ...`), no expanded local
paths (a root as the user would type it, such as `~/Documents`, is
fine), and nothing before the first line or after the last. One fact per bullet,
one sentence per bullet; split a bullet that needs two. Each bullet says something new: the hero states the claim, the
headline bullet states what the data supports and where a committed
figure would go, and the limitation bullet names a limitation the
headline lacks. A request to convert to money is declined in one
sentence as the first bullet of `## Report`, never ahead of the hero,
and says "money" or "currency", never a unit or the word "dollars". The
finance handoff (hours with their interval, the pinned window, and the
population, for finance to convert) is the next bullet.
An n<5 spread is a range (`range_lo`..`range_hi`, `measurement.md`); the reply never uses the words "95%" or "interval" for it, not even to deny them.
Name an unknown or a missing input, never a script's exit status or command. Every figure in the reply keeps its provenance tag, in the hero and
in bullets. State a figure as what was measured, never as what the
skill caused: "median 18 min per task gross, range 11..22 min, net unknown
(DIRECTIONAL, MEASURED, n=3)", not "the skill saved 18 min".
Write adoption and realization in words, never as `(a)` and `(r)`.
The hero is the measurement, with the word "gross" when net is unknown ("18 min median per
draft gross, range 11..22 min"), never an effect ("18 min less per draft"); a bullet
never repeats it. Cite a benchmark with its qualifier ("METR, early-2025 tools").

Reply in this shape:

```text
✓ Leadership report: net +310 engineer-hours per quarter projected, upside +520 (DERIVED)

## Run

- 2026-07-14/business/review-skill, window 2026-04-01..2026-06-30.

## Gate

- Passed: sources, assumptions, tags, and unknowns complete.

## Report

- Written to reports/leadership.md.
- Strongest limitation: review latency covers 41 PRs, one team.

Next, you can:
- Render the org-wide projection.
- Adjust an assumption and render again.
- Stop here.
```

The last list is the non-interactive form; with a question tool it is
the panel instead.

### Stopped run

A run that halts (run not found, gate failed, missing input, failed
sweep) is one hero line `⚠ Refused: <reason in one sentence>`, then
one short paragraph or list of what the user must do next, two
sentences at most. Never include:

- `Run`, `Gate`, or `Report` sections, or a panel.
- A list of checks performed.
- A sentence that repeats the hero, the run name, or a question already
  asked.
- The roots searched, when no run is found; say "no business run found".
  Never write a directory such as `~/Documents`.
- Negation narration ("I did not use a default") or a sandbox fact ("I
  cannot ask you here").
- A claim that a check failed when it did not run, an exit status the
  script does not define (`runs` prints nothing and exits 0 when it finds
  no run), or a description of references that were not loaded.

```text
⚠ Refused: sources.md has an entry with no output file.

Add the missing snapshot or remove the entry, then render again.
```

```text
⚠ Refused: no public case study for this run.

Run /business:case-study-public on it, then run /business:pr-release again.
```

### Paths and commits

Name a run as `<date>/business/<workflow>` relative to its root, and
a root as the user would type it (`~/Documents`), never expanded into
a temporary or sandbox path or a username-bearing path. Print an
absolute path only when the user must act on that file. Never report
sandbox restrictions as facts about the user's machine, and say what
you need from the user rather than what you could not read from here.

Steps that ask the user (`AskUserQuestion`) state their
non-interactive default; an explicit authorization in the request
covers only the action named.
