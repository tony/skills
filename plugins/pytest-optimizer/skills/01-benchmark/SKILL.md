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
(measurement runs per candidate, default matches the baseline), and `--force` to
re-benchmark ids already recorded.

## Step 1: Load inputs

Read `baseline.json` (noise band, test command, capabilities) and
`hypotheses.json` from the resolved memory directory. If either is missing, tell
the user to run `/pytest-optimizer:00-scan` first. If `git status --porcelain`
shows changes outside the memory directory, stop and ask the user to commit or
shelve them: the scratch worktree is cut from `HEAD`, so the baseline and the
candidates must measure the same commit. Substitute that resolved test
command wherever this file writes `pytest`. Skip any hypothesis whose
(content-derived) id already has a benchmark recorded **against the current
baseline token**, unless `--force`; a re-baseline after `03-execute` re-opens all
candidates for fresh measurement.

## Step 2: Per hypothesis — apply, measure, gate

For each open hypothesis, in isolation:

1. **Isolate.** Create a detached scratch worktree under the system temp
   directory and run everything below inside it:

   ```bash
   git worktree add --detach <scratch-dir> HEAD
   ```
2. **Apply** the single change the heuristic prescribes
   (`../../references/heuristic-catalog.md`).
3. **Measure.** Run the suite serially, cache disabled, `--runs` times, recording
   total wall-time:

   ```bash
   pytest -p no:cacheprovider -p no:randomly -q
   ```

   Compute the median delta (`baseline_median − candidate_median`) against
   `baseline.json`. It is a real speedup only if `median_delta > k·MAD`
   (default `k = 3`). Within the band means `impact = 0`: rejected.
4. **Safety gates** (`../../references/safety-gates.md`), required
   for any change touching order/scope/parallelism:
   - order independence (H17) across ≥ 3 seeds and in isolation;
   - collection determinism (H18);
   - green serial re-run.
   A gate failure rejects the candidate and surfaces the prerequisite refactor as
   its own follow-up hypothesis.
   - For a parallelism candidate (H19), also run it 5–10 times. If failures move
     between workers, try the grouping options (H20); if a session fixture fires
     once per worker, apply the single-exec pattern (H21). Both are in
     `../../references/safety-gates.md`.
5. **Discard** the scratch worktree and confirm the user's tree is untouched:

   ```bash
   git worktree remove --force <scratch-dir>
   ```

## Step 3: Record

Write `benchmarks.json`: per id, the applied-diff summary, run count, median
delta, `clears_noise`, gate results, a `confidence` score (serial + repeated
+ delta-above-floor → high), the observed risk, and a `verdict`
(`validated`/`rejected` + reason). Update `state.json`
(`phase=benchmark`, benchmarked ids). The phase is idempotent per id.

## Step 4: Report

Emit the `01-benchmark` sections from
`../../references/output-contract.md`. Write the prose per
`../../references/prose-rules.md`. Close with an
`AskUserQuestion` panel offering to build the plan, re-benchmark a subset, or stop.
