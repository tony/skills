---
name: research
description: "Use when collecting evidence for the business value of an AI skill or workflow into a provenance-tagged research package."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
argument-hint: "[skill or workflow to measure] [date range, e.g. 2026-04-01..2026-06-30]"
disable-model-invocation: true
---

# Business Research

Collect the data behind a business-value claim for an AI skill or
agentic workflow (productivity, time saved, quality, capacity,
delivery outcomes) into the interim run package the report skills
render from.

Read these first; they bind every step:

- `../../references/interim-format.md`: the run package layout, where
  runs live, and the value units (never money).
- `../../references/provenance.md`: the four tags and the
  anti-inflation rules.
- `../../references/instruments.md`: per-instrument probes,
  collection discipline, the pull-request query, and the targets to
  collect.

Load `../../references/measurement.md` only for the counterfactual
ladder and the statistics discipline, which owns the n<5 range rule.
Intervals come from `../../scripts/business.py stats` (absolute path).

User arguments: $ARGUMENTS

## Procedure

### 1. Scope and orchestration plan

Enter plan mode before the first edit. In Claude Code call
`EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or
`Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present the plan (shape below) and ask where to write the run,
defaulting per `interim-format.md` § Where runs live. Write nothing,
including `index.md`, until the user approves. Exit plan mode, then
open the run at the approved root with `business.py init`, per
`interim-format.md` § Where runs live. Pass `--date` when the request
names a dated run path; if `init` refuses, follow the same section.

Non-interactive (no question tool, headless): print the plan with the
default root and stop. A request that itself names the root approves
the plan; record the root in the run README and continue.

Reply in this shape (reply form per `interim-format.md` § Finished
run), with no greeting, naming roots as the user would type them:

```text
Plan: review-skill, window 2026-04-01..2026-06-30. Nothing is written yet.

## Measure

- Cycle time and first-review latency per PR; rework signals.
- Adoption and per-task timing only from exports you provide.

## Instruments

- git and gh to probe; trackers and timing logs only from exports you provide.

## Output

- 2026-07-14/business/review-skill under ~/Documents, the default root.
- Questions: confirm the root and the repo paths.
```

The `- Questions:` bullet is the last line: no closing paragraph that
restates it. One fact per bullet. Report what you will probe, not
what the current directory happens to hold or what you have not yet
probed.

### 2. Instrument discovery

Probe each instrument per `instruments.md`; never assume one exists.
Record every instrument as available or unavailable in the run
README (for `gh auth status`, only that it succeeded). Data an unavailable instrument would have provided is
`unknown`, never fabricated and never silently skipped, unless the
user supplies an assumption, which is registered as ESTIMATED with
rationale and owner (`provenance.md` gives its fields).

### 3. Collect

For each available instrument, run pinned-window queries per
`instruments.md` and snapshot raw output into `raw/` before deriving
anything. Collect the targets listed there; record the rest as
unknown. Derive pull-request tables with `business.py collect-prs`,
piping the query into it with `--output` so reviewer and author logins
never reach `raw/`, rather than rewriting the query or the filter. Write
every `sources.md` entry with `business.py source <run> <entry> <file>
--query <command> --tool-version <version>` (absolute path) right after the
command produces `<file>`: the script writes the output path, the clock
time, and the sha256, so none is typed by hand. Record every `collect-prs`
warning, including "rows lack" ones, in that entry and in the README.

### 4. Write the package

Fill the package `init` started, per `interim-format.md`: run README,
source manifest with verbatim queries, assumptions register, raw
snapshots, per-topic measurements, and `findings.md`. Tag every figure
per `provenance.md`; list every unknown with what data would resolve it.
List every organization, repository, team, and workflow name the run
touched on the README `Names:` line, and every individual on the
`People:` line (never on both); the scans depend on both.
Compute medians, quartiles, and intervals with `business.py stats`
(`--csv <file> --column <a-b>` for a CSV column); copy its `n`, `rows`,
and `dropped_blank` beside each statistic. Give each MEASURED
figure computed from a `raw/` CSV a `check:` line. Run
`business.py gate <run>` and fix every problem before reporting.
Write prose per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ Run written: <date>/business/<workflow>, window
<start>..<end>`; a stopped run follows `interim-format.md` §
Rendering a report. Then exactly these sections:

1. `## Scope`: what was measured and the pinned window.
2. `## Instruments`: available vs unavailable, and what each
   unavailable one leaves unknown.
3. `## Collected`: per instrument, what the data shows and what landed
   in `raw/` and `measurements/`; one fact per bullet, one sentence per
   bullet, with no clause defending a choice or restating the hero.
4. `## Package`: the run location, the count of registered assumptions
   (0 is valid; a measured count is not an assumption), and the count
   of open unknowns; the unknowns themselves stay in
   `findings.md`.

End with an `AskUserQuestion` panel: generate a report (ask which
tier), collect more, or stop.
Panel rules as in `interim-format.md` § Finished run.

Reply in this shape:

```text
✓ Run written: 2026-07-14/business/review-skill, window 2026-04-01..2026-06-30

## Scope

- Review latency and rework rate for the review skill, 41 PRs.

## Instruments

- Available: git history, gh pull-request data.
- Unavailable: timing logs; per-use verification time stays unknown.

## Collected

- raw/ holds 2 snapshots; measurements/ holds latency and rework.

## Package

- Run at 2026-07-14/business/review-skill, 3 assumptions, 1 open unknown.

Next, you can:
- Generate a report (leadership, org-wide, internal or public case study).
- Collect more data.
- Stop here.
```

The last list is the non-interactive form; with a question tool it is
the panel instead.
