---
name: 01-benchmark
description: "Use when benchmarking pytest optimization hypotheses from 00-scan in isolation to identify speedups that beat measured noise."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
argument-hint: "[--only=<heuristic-id>] [--runs=N] [--force] [--memory-dir=<path>]"
user-invocable: true
disable-model-invocation: true
---

# 01-benchmark

Prove or disprove each hypothesis by measurement. This phase applies candidates
only inside a scratch git worktree, never on the user's working tree or history.

`$ARGUMENTS` may pass `--only=<heuristic-id>` to benchmark a subset, `--runs=N`
(measurement runs per candidate, default matches the baseline), `--force` to
re-benchmark ids already recorded, and `--memory-dir` to override the memory
location.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard library).
Run it by its absolute path; the relative path is from this file, not the repo.

## Step 1: Load inputs

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists, or `baseline.json` or
`hypotheses.json` is missing, stop with the halted-run shape in
`../../references/output-contract.md` and tell the user to run
`pytest-optimizer:00-scan` first.

Read `baseline.json` (noise band, test counts, test command, capabilities) and
`hypotheses.json`. If `git status --porcelain` shows changes outside the memory
directory, stop and ask the user to commit or shelve them: the scratch worktree
is cut from `HEAD`, so the baseline and the candidates must measure the same
commit. Substitute the resolved test command wherever this file writes
`pytest`. Skip any hypothesis whose (content-derived) id already has a benchmark
recorded **against the current baseline token**, unless `--force`; a re-baseline
after `03-execute` re-opens all candidates for fresh measurement.

## Step 2: Per hypothesis — apply, measure, gate

For each open hypothesis, in isolation:

1. **Isolate.** Create the scratch directory; the command prints its path, so use
   that literal path in every later command:

   ```console
   $ mktemp -d "${TMPDIR:-/tmp}/pytest-optimizer.XXXXXX"
   ```

   Then add a detached worktree there and run everything below inside it, with
   the project's own interpreter and environment (the worktree has no virtualenv
   of its own):

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
   $ python3 ../../scripts/measure.py run \
       --cwd <scratch-dir> \
       -- pytest -p no:cacheprovider -p no:randomly -q
   ```

   Judge the runs against the baseline:

   ```console
   $ python3 ../../scripts/measure.py compare baseline.json <candidate runs file>
   ```

   A candidate counts only when `valid` is true (every run exits 0 and the
   passed and collected-test counts equal the baseline's) and `clears_noise` is
   true (`median_delta` exceeds the band, which is floored at the trust floor).
   `valid: false` or a delta within the band means `impact = 0`: rejected, with
   the reported reason. A change that removes tests on purpose passes
   `--expect-total <count>`.
4. **Safety gates** (`../../references/safety-gates.md`):
   - green serial run with unchanged test counts, for every change (the
     `valid` check above);
   - for a change touching order/scope/parallelism: order independence (H17)
     across ≥ 3 seeds and in isolation, and collection determinism (H18), using
     `measure.py order` on unsorted `--collect-only -q` output.
   A gate failure rejects the candidate and surfaces the prerequisite refactor as
   its own follow-up hypothesis.
   - For a parallelism candidate (H19), also run it 5–10 times. If failures move
     between workers, try the grouping options (H20); if a session fixture fires
     once per worker, apply the single-exec pattern (H21). Both are in
     `../../references/safety-gates.md`.
5. **Discard** the scratch worktree and prune its record:

   ```console
   $ git worktree remove --force <scratch-dir>
   ```

   ```console
   $ git worktree prune
   ```

   Confirm the user's tree is untouched: `git worktree list` shows only the main
   tree and `git status --porcelain` matches its state before the phase.

## Step 3: Record

Write `benchmarks.json`: per id, the applied-diff summary, run count, median
delta, `clears_noise`, gate results, a `confidence` score (serial + repeated
+ delta-above-floor → high), the observed risk, and a `verdict`
(`validated`/`rejected` + reason). Update `state.json`
(`phase=benchmark`, benchmarked ids). The phase is idempotent per id.

## Step 4: Report

Emit the `01-benchmark` sections from `../../references/output-contract.md`. Write
the prose per `../../references/prose-rules.md`.

Close with an `AskUserQuestion` panel offering to build the plan, re-benchmark a
subset, or stop. Without an interactive question tool, stop after the report and
name the next step in one sentence.
