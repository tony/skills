---
name: 02-plan
description: "Use when ranking validated pytest speedups from 01-benchmark into an approved, ordered, commit-by-commit plan."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
argument-hint: "[--max-commits=N] [--min-score=<0..1>] [--force] [--memory-dir=<path>]"
disable-model-invocation: true
---

# 02-plan

Turn measured candidates into a reviewable commit plan. This phase writes only
`plan.json` and `state.json`, and only after the user approves.

`$ARGUMENTS` may pass `--max-commits=N` to cap the plan, `--min-score` to raise the
inclusion threshold, `--force` to recompute, and `--memory-dir` to override the
memory location.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`../../scripts/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Load and score

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists or `benchmarks.json` is
missing, stop with the halted-run shape in `../../references/output-contract.md`
and tell the user to run `pytest-optimizer:01-benchmark` first.

Read `benchmarks.json`, `baseline.json` and `state.json`. The evidence must
still describe this checkout: `state.json` has `dirty` false, `git rev-parse HEAD`
equals its `base_head`, and every entry you score has an `env_token` equal to
its `env_token`, a `patch_sha256` and a `base_head` equal to it. Otherwise stop
with the halted-run shape and send the user to `pytest-optimizer:00-scan --force`
(a different `HEAD` or token) or `pytest-optimizer:01-benchmark --force` (an
entry with no token or patch).

Score every `validated` candidate with `../../references/scoring-rubric.md`: get
`impact` from `measure.py impact --delta <median_delta> --baseline <median>`,
adding `--clears-noise` only when that entry's `clears_noise` is true (a
validated entry where it is not true has impact 0 and is dropped), judge the
other four dimensions against the rubric anchors, then run `measure.py score`
with all five. It returns the total and a `dropped` reason.
A candidate benchmarked as `kind: "hygiene"` (H26-H32) has no timing: pass
`--hygiene` to `measure.py score` (impact 0), which skips the noise gate and
scores the other four dimensions. Plan it as a hygiene item, never drop it for
saving no time.

Drop every candidate whose `dropped` is set. Capture each dropped item's
prerequisite refactor, if any, as a labeled follow-up, never an auto-applied
commit.

## Step 2: Order

Score sets priority; the rubric's ordering constraints override it. One speedup
per commit, never bundled. Honor `--max-commits` and `--min-score`.

## Step 3: Draft commits

For each planned item, draft a commit from
`../../templates/commit-message.tmpl`, adapting the `type(scope)` prefix to the
target project's convention. Write the message per
`../../references/prose-rules.md`. No `Co-Authored-By`, no "Generated with" or
other tool trailer, no emoji: hosts add them by default. Each entry records
order, heuristic id, score breakdown, target files, draft subject and body, the
verify command (project tests and quality checks), the entry's `env_token`,
`patch`, `patch_sha256`, `files`, `cache` and `removed_ids`, `expected_total` (the
collected-test count after this item and every earlier item apply: the baseline
`tests.total`, less the tests each earlier or current deselecting item removes), and
`depends_on`. The approval reply shows the draft subject only; the body goes into `plan.json` on approval. Keep the draft in the reply, not on disk: nothing is written until
approval.

Confirm each path in `files` exists at `HEAD`, unless the patch creates it. An
item whose target is absent is not planned: list it under `## Dropped at the
gate` with "target file absent at HEAD", and count only the kept items in the
hero line. A deselecting item (`removes_tests` in `benchmarks.json`) states "removes
N tests from the default run" and sets `expected_total` to the reduced count, carries that count into every later item's `expected_total`, and
its saving reads as time not spent on those tests, not as a faster suite.

Each saving was measured alone against the control. Independent changes can
overlap (widening a sleeping fixture and removing its sleep do not add), so
never sum the savings or call them recovered: the plan states each as measured
alone, and `03-execute` measures the combined result.

## Step 4: Present for approval

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present the `02-plan`
sections from `../../references/output-contract.md`. Let the user reorder, drop
items, or cap the count; revise the draft in the reply after each change and write
nothing, since plan mode blocks writes. Plan mode is the decision point, so omit
the `AskUserQuestion` panel.

Without plan mode, the reply is the same sections as text and nothing else: the
hero line comes first and carries the approval request, with no remark about plan
mode before it and no closing note after the last section. Wait for the reply:

```text
✓ 1 commit planned; reply "approve" to record the plan, or name items to drop or reorder

## Ranked plan

- 1. H10 mis-scoped fixture: widen make_config to session scope in tests/conftest.py under the subject "tests(fixtures) Widen make_config to session scope", total score 0.87, saved 2.7s measured alone above the 0.44s band, verified with pytest expecting 40 of 40 passing.
```

Without an interactive session, write nothing and stop: an unapproved plan is not
executable.

Once the user approves, exit plan mode, write `plan.json` from the approved
draft, then record approval:

```console
$ python3 <measure.py> hash <memory-dir>/plan.json
```

Store that value as `plan_hash` and set `phase=plan` and `completed.plan=true` in
`state.json`.
`plan.json` is the contract `pytest-optimizer:03-execute` consumes; a request that
explicitly says to approve and apply the plan is approval for this plan only.
