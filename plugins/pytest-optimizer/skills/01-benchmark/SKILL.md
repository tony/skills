---
name: 01-benchmark
description: "Use when benchmarking pytest optimization hypotheses from 00-scan in isolation to identify speedups that beat measured noise."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
argument-hint: "[--only=<heuristic-id>] [--runs=N] [--force] [--memory-dir=<path>]"
user-invocable: true
disable-model-invocation: true
---

# 01-benchmark

Prove or disprove each hypothesis by measurement, applying candidates only
inside a scratch git worktree, never on the user's working tree or history.

`$ARGUMENTS` may pass `--only=<heuristic-id>` to benchmark a subset, `--runs=N`
(measurement runs per candidate, default matches the baseline), `--force` to
re-benchmark ids already recorded, and `--memory-dir` to override the memory
location.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`../../scripts/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Load inputs

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists, or `baseline.json` or
`hypotheses.json` is missing, stop with the halted-run shape in
`../../references/output-contract.md` and tell the user to run
`pytest-optimizer:00-scan` first.

Recompute the idempotency token as `00-scan` Step 2 does. If `state.json`
records an `env_token` and the result differs, the baseline is stale: stop and tell the user to run
`pytest-optimizer:00-scan --force`.

Read `baseline.json` and `hypotheses.json`. If `git status --porcelain` shows
changes outside the memory directory, stop and ask the user to commit or shelve
them: the scratch worktree is cut from `HEAD`, which the baseline must match.
Substitute `test_command` from `baseline.json` wherever this file writes
`pytest`. Skip a hypothesis whose id already has a benchmark recorded **against the current
baseline token**, unless `--force`.

## Step 2: Per hypothesis — apply, measure, gate

For each open hypothesis, in isolation:

1. **Isolate.** Refuse when `git rev-parse --show-toplevel` prints `$HOME` or a
   directory containing it. Create the scratch directory; the command prints its
   path, so use that literal path in every later command:

   ```console
   $ mktemp -d "${TMPDIR:-/tmp}/pytest-optimizer.XXXXXX"
   ```

   Then add a detached worktree there and run everything below inside it with
   the project's own runner. The worktree holds only tracked files: no virtualenv
   and no gitignored build artifacts. Rebuild them there with the project's
   install or sync command (`uv run` builds a fresh `.venv` on first use, which
   the untimed warm-up absorbs), or mark the hypothesis `rejected` when the suite
   cannot run from a clean checkout:

   ```console
   $ git worktree add --detach <scratch-dir> HEAD
   ```

   An editable install imports the original tree, so a hypothesis that edits
   package source cannot be measured this way; mark it `rejected` with that
   reason.
2. **Apply** the single change the heuristic prescribes
   (`../../references/heuristic-catalog.md`).
3. **Measure.** Run the suite serially, cache disabled, once untimed as a warm-up
   and then `--runs` times, appending each JSON line to a candidate runs file:

   ```console
   $ python3 <measure.py> run \
       --cwd <scratch-dir> \
       -- pytest -p no:cacheprovider -p no:randomly -q
   ```

   Judge the runs against the baseline:

   ```console
   $ python3 <measure.py> compare baseline.json <candidate runs file>
   ```

   A candidate counts only when `valid` is true and `clears_noise` is true.
   Otherwise `impact = 0` and it is rejected with the reported reason. A change
   that removes tests on purpose passes `--expect-total <count>`.
4. **Safety gates** per `../../references/safety-gates.md`: the `valid` check
   above for every change; order independence (H17) and collection determinism
   (H18) for a change touching order, scope, or parallelism. A gate failure
   rejects the candidate and surfaces the prerequisite refactor as its own
   follow-up hypothesis. A parallelism candidate (H19) also runs 5-10 times,
   with the grouping (H20) and single-exec (H21) fixes from the same reference.
5. **Discard** the scratch worktree and prune its record:

   ```console
   $ git worktree remove --force <scratch-dir>
   ```

   ```console
   $ git worktree prune
   ```

   Confirm `git worktree list` shows only the main tree and `git status
   --porcelain` matches its state before the phase.

## Step 3: Record

Write `benchmarks.json` in the shape `../../references/memory-schema.md` gives,
with `confidence` high only for serial, repeated runs with the delta above the
floor. Update `state.json` (`phase=benchmark`, benchmarked ids).

## Step 4: Report

Emit the `01-benchmark` sections from `../../references/output-contract.md`. Write
the prose per `../../references/prose-rules.md`.

Close with an `AskUserQuestion` panel offering to build the plan, re-benchmark a
subset, or stop. Without one, stop after the report and name the next step in
one sentence.
