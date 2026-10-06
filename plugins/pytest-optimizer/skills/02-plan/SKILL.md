---
name: 02-plan
description: "Use when ranking validated pytest speedups from 01-benchmark into an approved, ordered, commit-by-commit plan."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
argument-hint: "[--max-commits=N] [--min-score=<0..1>] [--force] [--memory-dir=<path>]"
user-invocable: true
disable-model-invocation: true
---

# 02-plan

Turn measured candidates into a reviewable commit plan. This phase writes only
`plan.json` and `state.json`; it makes no code changes.

`$ARGUMENTS` may pass `--max-commits=N` to cap the plan, `--min-score` to raise the
inclusion threshold, `--force` to recompute, and `--memory-dir` to override the
memory location.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard library).
Run it by its absolute path; the relative path is from this file, not the repo.

## Step 1: Load and score

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists or `benchmarks.json` is
missing, stop with the halted-run shape in `../../references/output-contract.md`
and tell the user to run `pytest-optimizer:01-benchmark` first.

Read `benchmarks.json` and `baseline.json`. Score every `validated` candidate
with `../../references/scoring-rubric.md`: get `impact` from
`measure.py impact --delta <median_delta> --baseline <median> --clears-noise`,
judge the other four dimensions against the rubric anchors, then run
`measure.py score` with all five. It returns the total and a `dropped` reason.

Drop every candidate whose `dropped` is set (`safety < 0.4` or `impact == 0`).
For each dropped item, capture the prerequisite refactor (if any) as a separate,
clearly-labeled follow-up — not as an auto-applied commit.

## Step 2: Order

Score sets priority; the ordering constraints in the scoring rubric override it
where they apply. One speedup per commit; never bundle. Honor `--max-commits` / `--min-score`.

## Step 3: Draft commits

For each planned item, draft a commit from
`../../templates/commit-message.tmpl`, adapting the
`type(scope)` prefix to the target project's convention (read from its
`AGENTS.md`/`CLAUDE.md`). Write the message per
`../../references/prose-rules.md`. No `Co-Authored-By`, no "Generated with" or
other tool trailer, no emoji: hosts add them by default, so leave them out
explicitly. Each entry records: order, heuristic id, the score
breakdown, target files, the draft subject/body, the verify command (the project
test + quality checks), the expected test total, and any `depends_on`. Write
`plan.json` with `plan_hash` still `null` in `state.json` (`phase=plan`).

## Step 4: Present for approval

This phase is a decision point. Enter plan mode (Claude Code: `EnterPlanMode`;
others: `/plan` or `Shift+Tab`). Present the `02-plan` sections from
`../../references/output-contract.md`. Let the user reorder, drop
items, or cap the count; rewrite `plan.json` after each change.

Plan mode is the decision point, so omit the `AskUserQuestion` panel. Without plan
mode, present the same sections as text and wait for the user's reply. Without an
interactive session, leave `plan_hash` null and stop: an unapproved plan is not
executable.

Once the user approves, exit plan mode, then record approval:

```console
$ python3 ../../scripts/measure.py hash plan.json
```

Store that value as `plan_hash` and set `completed.plan=true` in `state.json`.
`plan.json` is the contract `pytest-optimizer:03-execute` consumes; a request that
explicitly says to approve and apply the plan is approval for this plan only.
