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

Read `baseline.json` and `hypotheses.json`. If `git status --porcelain
--untracked-files=no` shows changes outside the memory directory, stop and ask
the user to commit or shelve them: the scratch worktree is cut from `HEAD`,
which the baseline must match. Untracked files never matter, because the
worktree holds only tracked files.
Substitute `test_command` from `baseline.json` wherever this file writes
`pytest`. Skip a hypothesis whose id already has a `benchmarks.json` entry whose
`env_token` equals `state.json`'s, unless `--force`.

Resolve `<runs-dir>` as `../../references/memory-schema.md` ("Run files") says
and create it. Delete each run file before its first timed run.

## Step 2: Budget, control run, then each hypothesis

**Budget.** Time one run of `test_command` to get `t` (the baseline median
works). The phase costs about `(runs + 1) * t` for the control plus the same for
every open speed hypothesis. Above the default budget of 1800 seconds in total
(the project's own limit, when its docs set one, replaces it), ask the user to
confirm, narrow with `--only`, or lower `--runs`. Without an interactive
question tool, benchmark only as many hypotheses as fit in 1800 seconds, lowest
prior risk and effort first, leave the rest `open`, and say so in the closing
line.

**Control run.** The baseline ran in the user's tree; candidates run in a fresh
worktree with no bytecode cache and a new virtualenv, so the two differ before
any change. Run the per-hypothesis steps 1, 3 and 5 once with no change applied, append its runs to
`<runs-dir>/control-runs.jsonl`, and save its summary in the memory directory:

```console
$ python3 <measure.py> band <runs-dir>/control-runs.jsonl > <memory-dir>/control.json
```

When `band` exits 1 the control run is invalid (non-zero exit or a changed
test count): stop, report its `reason` in one sentence, and run no candidate.

Judge every candidate against `control.json`, not `baseline.json`. When the
control's median differs from the baseline's by more than the baseline band,
say so in the closing line: absolute times from this phase are not comparable
to the baseline's. When it does not differ, say nothing about the control.

**Per hypothesis.** For each open hypothesis, in isolation:

1. **Isolate.** Refuse when `git rev-parse --show-toplevel` equals or contains
   the physical home directory (`(cd ~ && pwd -P)`; never compare to the string `$HOME`). Create the scratch directory; the command prints its
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

   When the host refuses the worktree (it writes under the git directory), fall
   back to an export of `HEAD` into the scratch directory, and skip the
   `git worktree remove` in step 5:

   ```console
   $ git archive HEAD | tar -x -C <scratch-dir>
   ```

   An editable install imports the original tree, so a hypothesis that edits
   package source cannot be measured this way; mark it `rejected` with that
   reason.
2. **Apply** the single change the heuristic prescribes
   (`../../references/heuristic-catalog.md`).
3. **Measure.** Run the suite serially, cache disabled, once untimed as a warm-up
   and then `--runs` times, appending each JSON line to
   `<runs-dir>/<hypothesis-id>-runs.jsonl`:

   ```console
   $ python3 <measure.py> run \
       --cwd <scratch-dir> \
       -- pytest -p no:cacheprovider -p no:randomly -q \
       >> <runs-dir>/<hypothesis-id>-runs.jsonl
   ```

   Judge the runs against the control:

   ```console
   $ python3 <measure.py> compare <memory-dir>/control.json <runs-dir>/<hypothesis-id>-runs.jsonl
   ```

   A candidate counts only when `valid` is true and `clears_noise` is true.
   Otherwise `impact = 0` and it is rejected with the reported reason. A count
   drop is a rejection naming the tests lost; it never counts as a speedup unless
   the change is a deliberate deselection below.

   A cross-run cache candidate (H24) measures with the cache provider enabled:
   drop `-p no:cacheprovider` for it, so the untimed warm-up populates the cache
   and the timed runs hit it. Its saving applies from the second run onward;
   say so in the record.

   A deselecting candidate (H15, H37) wins by running fewer tests, so it passes
   `--expect-total <count>`, records `removes_tests` with the number dropped, and
   reports the saving as time not spent on those tests. `02-plan` shows that
   number at the approval gate.

   A typing or parametrize hypothesis (H26-H32) saves no time by design: skip the
   timing. Run the suite once and the project's type checker over the test
   directory; it counts when both pass and the test count is unchanged. Record it
   with `kind: "hygiene"` and `median_delta` and `clears_noise` null.
4. **Safety gates** per `../../references/safety-gates.md`: the `valid` check
   above for every change; order independence (H17) and collection determinism
   (H18) for a change touching order, scope, or parallelism. A gate failure
   rejects the candidate and surfaces the prerequisite refactor as its own
   follow-up hypothesis. A parallelism candidate (H19) also runs 5-10 times,
   with the grouping (H20) and single-exec (H21) fixes from the same reference.
   H19 measures the control command (serial, as in step 3) and the same command
   plus `-n auto`, both recorded, the second as parallel; the no-xdist rule
   covers every other candidate.
5. **Discard** the scratch worktree and prune its record (an exported copy is just deleted with `rm -rf <scratch-dir>`, a path this run created):

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
stamping each entry with `state.json`'s `env_token`. Keep the entries for ids this
run skipped (`--only` or a matching token) and replace those for ids it
benchmarked, `--force` included. Set `confidence` high only for serial, repeated runs with the delta above the
floor. Nothing in this phase touches the user's tree, history, or any remote. Update
`state.json` (`phase=benchmark`, `completed.benchmark=true`, the later
`completed` flags false).

## Step 4: Report

Emit the `01-benchmark` sections from `../../references/output-contract.md`. Write
the prose per `../../references/prose-rules.md`. Put each candidate under the
section its measurement earned: a candidate rejected for a count drop or a gate
failure is under `## Rejected`, never `## Validated`. An empty section says
"None." in one line. Advise nothing the runs did not measure (no "make X
cheaper"). When the phase halted before any run, print the halted-run shape
instead, with one cause and no list of what is absent. Reply in this shape, as
plain text outside any code fence, with plain bullets, no bold (never
`- **Label:** ...`), and no local paths:

```text
✓ 1 validated, 1 rejected

## Validated

- H10 mis-scoped fixture: db_session to session scope saves 4.6s, above the 0.44s band, confidence 0.9.

## Rejected

- H33 fixed sleep in test_report: removing it saves 0.02s, inside the noise band.

## Safety-gate results

- H10 mis-scoped fixture: order independence held across 3 seeds and collection is deterministic.
```

Close with an `AskUserQuestion` panel offering to build the plan, re-benchmark a
subset, or stop. Without one, stop after the report and name the single next step in
one sentence, not a list of options.
