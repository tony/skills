---
name: research
description: "Use when collecting evidence for the business value of an AI skill or workflow into a provenance-tagged research package."
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion", "EnterPlanMode"]
argument-hint: "[skill or workflow to measure] [date range, e.g. 2026-04-01..2026-06-30]"
user-invocable: true
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
- `../../references/provenance.md`: the four tags, the anti-inflation
  rules, and the no-currency contract.
- `../../references/measurement.md`: what the data must feed: the
  saving formulas, statistics discipline, the counterfactual ladder,
  and the quality guardrails.
- `../../references/instruments.md`: per-instrument probes,
  collection discipline, and the collection targets in query-ready
  form.

User arguments: $ARGUMENTS

## Procedure

### 1. Scope and orchestration plan

Present an orchestration plan before touching disk: what will be
measured, over what pinned date range, with which instruments, to
which output directory. Enter plan mode if the host supports it:
Claude Code `EnterPlanMode`; Cursor, Codex, or Gemini via `/plan` or
Shift+Tab; otherwise present the plan as plain text and pause. Ask
where to write the run, defaulting per `interim-format.md` § Where
runs live, and open it there. Wait for confirmation.

### 2. Instrument discovery

Probe each instrument per `instruments.md`; never assume one exists.
Record every instrument as available or unavailable in the run
README. Data an unavailable instrument would have provided is
`unknown`, never fabricated and never silently skipped, unless the
user supplies an assumption, which is registered as ESTIMATED with
rationale and owner.

### 3. Collect

For each available instrument, run pinned-window queries per
`instruments.md` and snapshot raw output into `raw/` before deriving
anything. Collect the targets listed there; record the rest as
unknown.

### 4. Write the package

Emit the full interim format from `interim-format.md`: run README,
source manifest with verbatim queries, assumptions register, raw
snapshots, per-topic measurements, and `findings.md`. Every figure
tagged; every unknown listed with what data would resolve it. Write
prose per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ Run written: <run path>, window <start>..<end>`;
failure form `⚠ Refused: <reason>`. Then exactly these sections:

1. `## Scope`: what was measured and the pinned window.
2. `## Instruments`: available vs unavailable, and what each
   unavailable one leaves unknown.
3. `## Collected`: per instrument, what landed in `raw/` and
   `measurements/`.
4. `## Package`: the run path, count of registered assumptions, and
   the open unknowns.

End with an `AskUserQuestion` panel: generate a report (ask which
tier), collect more, or stop. Skip the panel in plan mode or when
running non-interactively.
