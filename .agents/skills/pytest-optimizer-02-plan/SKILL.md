---
name: pytest-optimizer-02-plan
description: >-
  Use when ranking validated pytest speedups from 01-benchmark into an
  approved, ordered, commit-by-commit plan.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--max-commits=N] [--min-score=<0..1>] [--force] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/02-plan/SKILL.md"
---

# 02-plan

Turn measured candidates into a reviewable commit plan. This phase writes only
`plan.json` and `state.json`.

`$ARGUMENTS` may pass `--max-commits=N` to cap the plan, `--min-score` to raise the
inclusion threshold, `--force` to recompute, and `--memory-dir` to override the
memory location.

Arithmetic goes through `references/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`references/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Load and score

Resolve the memory directory by the lookup order in
`references/memory-schema.md`. If none exists or `benchmarks.json` is
missing, stop with the halted-run shape in `references/output-contract.md`
and tell the user to run `pytest-optimizer:01-benchmark` first.

Read `benchmarks.json` and `baseline.json`. Score every `validated` candidate
with `references/scoring-rubric.md`: get `impact` from
`measure.py impact --delta <median_delta> --baseline <median> --clears-noise`,
judge the other four dimensions against the rubric anchors, then run
`measure.py score` with all five. It returns the total and a `dropped` reason.

Drop every candidate whose `dropped` is set. Capture each dropped item's
prerequisite refactor, if any, as a labeled follow-up, never an auto-applied
commit.

## Step 2: Order

Score sets priority; the rubric's ordering constraints override it. One speedup
per commit, never bundled. Honor `--max-commits` and `--min-score`.

## Step 3: Draft commits

For each planned item, draft a commit from
`templates/commit-message.tmpl`, adapting the `type(scope)` prefix to the
target project's convention. Write the message per
`references/prose-rules.md`. No `Co-Authored-By`, no "Generated with" or
other tool trailer, no emoji: hosts add them by default. Each entry records
order, heuristic id, score breakdown, target files, draft subject and body, the
verify command (project tests and quality checks), `expected_total` (the
baseline `tests.total`, unless the change removes tests on purpose), and
`depends_on`. Write `plan.json` with `plan_hash` still `null` in `state.json`
(`phase=plan`).

## Step 4: Present for approval

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present the `02-plan`
sections from `references/output-contract.md`. Let the user reorder, drop
items, or cap the count; rewrite `plan.json` after each change. Plan mode is the
decision point, so omit the `ask-user-choice` panel.

Without plan mode, present the same sections as text and wait for the reply.
Without an interactive session, leave `plan_hash` null and stop: an unapproved
plan is not executable.

Once the user approves, exit plan mode, then record approval:

```console
$ python3 <measure.py> hash plan.json
```

Store that value as `plan_hash` and set `completed.plan=true` in `state.json`.
`plan.json` is the contract `pytest-optimizer:03-execute` consumes; a request that
explicitly says to approve and apply the plan is approval for this plan only.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
