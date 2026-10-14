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
`plan.json` and `state.json`, and only after the user approves.

`$ARGUMENTS` may pass `--max-commits=N` to cap the plan, `--min-score` to raise the
inclusion threshold, `--force` to recompute, and `--memory-dir` to override the
memory location.

Arithmetic goes through `references/measure.py` and the staleness check
through `references/isolate.py` (Python 3 standard library). Both paths
resolve from this skill's own directory, not the project's working directory:
resolve this file's directory, join each path, print the absolute paths once,
and write those literal paths in each command below where `<measure.py>` and
`<isolate.py>` appear.

## Step 1: Load and score

Resolve the memory directory by the lookup order in
`references/memory-schema.md`. If none exists or `benchmarks.json` is
missing, stop with the halted-run shape in `references/output-contract.md`
and tell the user to run `pytest-optimizer:01-benchmark` first.

Read `benchmarks.json`, `baseline.json` and `state.json`. The evidence must
still describe this checkout (a clean scan at this `HEAD`, and every validated
entry carrying the scan's `env_token`, a `patch_sha256` and this `HEAD` as its
`base_head`):

```console
$ python3 <isolate.py> stale \
    --memory-dir <memory-dir> \
    --phase plan
```

On exit 1, stop with the halted-run shape and send the user to the phase its
`rerun` names (`pytest-optimizer:` followed by it).

Score every `validated` candidate with `references/scoring-rubric.md`: get
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
`templates/commit-message.tmpl`, adapting the `type(scope)` prefix to the
target project's convention. Write the message per
`references/prose-rules.md`. No `Co-Authored-By`, no "Generated with" or
other tool trailer, no emoji: hosts add them by default. Each entry records
order, heuristic id, score breakdown, target files, draft subject and body, the
verify command (project tests and quality checks), the entry's `env_token`,
`patch`, `patch_sha256`, `files`, `cache` and `removed_ids`, `expected_total`
(the collected-test count after this item and every earlier item apply), and
`depends_on`. Write the drafted orders and each item's `removes_tests` (0 when it
deselects nothing) to a scratch JSON list and take every `expected_total` from
the script, never by hand:

```console
$ python3 <measure.py> totals \
    <memory-dir>/baseline.json \
    <draft.json>
```
 The approval reply shows the draft subject only; the body goes into `plan.json` on approval. Keep the draft in the reply, not on disk: nothing is written until
approval.

Confirm each path in `files` exists at `HEAD` (paths are relative to the
repository root; exit 1 means absent), unless the patch creates it:

```console
$ git cat-file -e HEAD:<path>
```

An item whose target is absent is not planned: list it under `## Dropped at the
gate` with "target file absent at HEAD", and count only the kept items in the
hero line. A deselecting item (`removes_tests` in `benchmarks.json`) states "removes
N tests from the default run", and its saving reads as time not spent on those
tests, not as a faster suite.

Each saving was measured alone against the control. Independent changes can
overlap (widening a sleeping fixture and removing its sleep do not add), so
never sum the savings or call them recovered: the plan states each as measured
alone, and `03-execute` measures the combined result.

## Step 4: Present for approval

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present the `02-plan`
sections from `references/output-contract.md`. Let the user reorder, drop
items, or cap the count; revise the draft in the reply after each change and write
nothing, since plan mode blocks writes. Plan mode is the decision point, so omit
the `ask-user-choice` panel.

Without plan mode, the reply is the same sections as text and nothing else: the
hero line comes first and carries the approval request, with no remark about plan
mode before it and no closing note after the last section. Wait for the reply:

```text
✓ 1 commit planned; reply "approve" to record the plan, or name items to drop or reorder

## Ranked plan

- 1. H10 mis-scoped fixture: widen make_config to session scope in tests/conftest.py under the subject "tests(fixtures) Widen make_config to session scope", total score 0.87, saved 2.7s measured alone above the 0.44s band, verified with pytest expecting 40 of 40 passing.

## Dropped at the gate

- H33 fixed sleep in test_report: saves 0.03s, inside the noise band, so impact is 0.
```

Without an interactive session, write nothing and stop: an unapproved plan is not
executable.

Once the user approves, exit plan mode, write `plan.json` from the approved
draft, then record approval:

```console
$ python3 <measure.py> hash <memory-dir>/plan.json
```

Record the approval, which clears the later flags:

```console
$ python3 <measure.py> state \
    complete <memory-dir>/state.json \
    --phase plan \
    --set 'plan_hash="<hash>"'
```

`plan.json` is the contract `pytest-optimizer:03-execute` consumes; a request that
explicitly says to approve and apply the plan is approval for this plan only.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
