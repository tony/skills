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
`plan.json`; it makes no code changes.

`$ARGUMENTS` may pass `--max-commits=N` to cap the plan, `--min-score` to raise the
inclusion threshold, and `--force` to recompute.

## Step 1: Load and score

Read `benchmarks.json` and `baseline.json`. Score every `validated` candidate
with the formula in `../../references/scoring-rubric.md`.

Apply the hard gates first: drop any candidate with `safety < 0.4` or
`impact == 0`. For each dropped item, capture the prerequisite refactor (if any)
as a separate, clearly-labeled follow-up — not as an auto-applied commit.

## Step 2: Order

Score sets priority; the ordering constraints in the scoring rubric override it
where they apply. One speedup per commit; never bundle. Honor `--max-commits` / `--min-score`.

## Step 3: Draft commits

For each planned item, draft a commit from
`../../templates/commit-message.tmpl`, adapting the
`type(scope)` prefix to the target project's convention (read from its
`AGENTS.md`/`CLAUDE.md`). Write the message per
`../../references/prose-rules.md`. Each entry records: order, heuristic id, the score
breakdown, target files, the draft subject/body, the verify command (the project
test + quality checks), and any `depends_on`. Write `plan.json` and update
`state.json` (`phase=plan`, plan hash).

## Step 4: Present for approval (plan mode)

This phase is a decision point. Enter plan mode (Claude Code: `EnterPlanMode`;
others: `/plan` or `Shift+Tab`). Present the `02-plan` sections from
`../../references/output-contract.md`. Let the user reorder, drop
items, or cap the count. Because plan mode is the decision point, omit the
`AskUserQuestion` panel here. Exit plan mode once approved; `plan.json` is the
contract `/pytest-optimizer:03-execute` consumes.
