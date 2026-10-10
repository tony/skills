---
name: pytest-optimizer-01-benchmark
description: >-
  Use when benchmarking pytest optimization hypotheses from 00-scan in
  isolation to identify speedups that beat measured noise.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[--only=<heuristic-id>] [--runs=N] [--force] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/01-benchmark/SKILL.md"
---

# 01-benchmark

Prove or disprove each hypothesis by measurement, applying candidates only
inside an owned scratch worktree, never on the user's working tree or history,
and keep each validated change as a hash-bound patch for `03-execute`.

`$ARGUMENTS` may pass `--only=<heuristic-id>` to benchmark a subset, `--runs=N`
(measurement runs per candidate, default matches the baseline), `--force` to
re-benchmark ids already recorded, and `--memory-dir` to override the memory
location.

Arithmetic goes through `references/measure.py` and scratch worktrees and
patches through `references/isolate.py` (Python 3 standard library). Both
paths resolve from this skill's own directory, not the project's working
directory: resolve this file's directory, join each path, print the absolute
paths once, and write those literal paths in each command below where
`<measure.py>` and `<isolate.py>` appear.

## Step 1: Load inputs

Resolve the memory directory by the lookup order in
`references/memory-schema.md`. If none exists, or `baseline.json` or
`hypotheses.json` is missing, stop with the halted-run shape in
`references/output-contract.md` and tell the user to run
`pytest-optimizer:00-scan` first.

Check that the baseline still describes this checkout, naming the first
failure only. `state.json` must hold an `env_token` and `dirty` false;
`git rev-parse HEAD` must equal its `base_head`; the `digest` from
`python3 <isolate.py> inputs --cwd .` must equal its `inputs_digest`; and the
project's test command must equal `baseline.json`'s `test_command`, and so must
the runner's `pytest --version` when `baseline.json` records `pytest_version`.
Any miss means the baseline is stale or came
from a dirty tree: tell the user to commit or shelve their changes and run
`pytest-optimizer:00-scan --force`. Then `git status --porcelain
--untracked-files=all` must show nothing outside the memory directory; otherwise
stop and ask the user to commit or shelve it, since the scratch worktree is cut
from `HEAD` and lacks tracked edits and untracked files the baseline ran with.

Read `baseline.json` and `hypotheses.json`. Substitute `test_command` from `baseline.json` wherever this file writes
`pytest`. Skip a hypothesis whose id already has a `benchmarks.json` entry whose
`env_token` equals `state.json`'s, unless `--force`.

Resolve `<runs-dir>` as `references/memory-schema.md` ("Run files") says
and create it. Delete each run file before its first timed run.

## Step 2: Budget, control run, then each hypothesis

**Budget.** Time one run of `test_command` to get `t` (the baseline median
works). The phase costs about `(runs + 1) * t` for the control plus the same for
every open speed hypothesis. Above the default budget of 1800 seconds in total
(the project's own limit, when its docs set one, replaces it), ask the user to
confirm, narrow with `--only`, or lower `--runs`. Without an interactive
question tool, benchmark only as many hypotheses as fit in that budget, lowest
prior risk and effort first, leave the rest `open`, and say so in the closing
line; when not even the control fits, stop and print the estimate.

**Control run.** The baseline ran in the user's tree; candidates run in a fresh
worktree with no bytecode cache and a new virtualenv, so the two differ before
any change. Run the per-hypothesis steps 1, 3 and 5 once with no change applied (step 3 passes `--min-runs 3` and `--cwd`), append its runs to
`<runs-dir>/control-runs.jsonl`, and save its summary in the memory directory:

```console
$ python3 <measure.py> band <runs-dir>/control-runs.jsonl > <memory-dir>/control.json
```

When `band` exits 1 the control run is invalid (non-zero exit, too few runs,
unavailable or changed test counts): stop, report its `reason` in one sentence, and run no candidate.

Judge every candidate against `control.json`, not `baseline.json`. When the
control's median differs from the baseline's by more than the baseline band,
say so in the closing line: absolute times from this phase are not comparable
to the baseline's. When it does not differ, say nothing about the control.

**Per hypothesis.** For each open hypothesis, in isolation:

1. **Isolate.** Refuse when `git rev-parse --show-toplevel` equals or contains
   the physical home directory (`(cd ~ && pwd -P)`; never compare to the string
   `$HOME`). Create an owned scratch worktree at the baseline commit; the command
   prints its `dir` and `tree`, so use those literal paths in every later command:

   ```console
   $ python3 <isolate.py> start \
       --repo . \
       --base <base_head>
   ```

   Run everything below inside `tree` with the project's own runner. The worktree
   holds only tracked files: no virtualenv and no gitignored build artifacts.
   Rebuild them there with the project's install or sync command (`uv run`
   builds a fresh `.venv` on first use, which the untimed warm-up absorbs), or
   mark the hypothesis `rejected` when the suite cannot run from a clean
   checkout.

   When the host refuses the worktree (it writes under the git directory), add
   `--export` to the command: the scratch directory then holds a copy of
   `base_head` in its own one-commit repository, and every later command works
   the same.

   An editable install imports the original tree, so a hypothesis that edits
   package source cannot be measured this way; mark it `rejected` with that
   reason.
2. **Apply** the single change the heuristic prescribes
   (`references/heuristic-catalog.md`), then capture it before running
   anything, since every file a run creates would enter the patch:

   ```console
   $ python3 <isolate.py> capture \
       --cwd <tree> \
       --out <memory-dir>/patches/<hypothesis-id>.patch
   ```

   Create `patches/` first. The output holds the patch's `sha256` and `paths`;
   `03-execute` applies exactly these bytes.
3. **Measure.** Run the measurement command
   (`references/durations-parsing.md`) once untimed as a warm-up and then
   `--runs` times, appending each JSON line to
   `<runs-dir>/<hypothesis-id>-runs.jsonl`:

   ```console
   $ python3 <measure.py> run \
       --cwd <tree> \
       -- pytest -p no:cacheprovider -p no:randomly \
       >> <runs-dir>/<hypothesis-id>-runs.jsonl
   ```

   Judge the runs against the control:

   ```console
   $ python3 <measure.py> compare <memory-dir>/control.json <runs-dir>/<hypothesis-id>-runs.jsonl
   ```

   When `valid`, write the listing from `test_command` run in the tree, as
   `00-scan` Step 2 does, and compare node ids with the scan's:

   ```console
   $ python3 <measure.py> ids \
       <memory-dir>/collection.txt \
       <runs-dir>/<hypothesis-id>-collection.txt
   ```

   A candidate counts only when `valid` is true, `clears_noise` is true, and the
   ids are `same`, unless it is a deliberate deselection or hygiene change
   below. Equal counts alone would pass a swapped test.
   Otherwise `impact = 0` and it is rejected with the reported reason. A count
   drop is a rejection naming the tests lost; it never counts as a speedup unless
   the change is a deliberate deselection below.

   A cross-run cache candidate (H24) measures with the cache provider enabled:
   drop `-p no:cacheprovider` for it, so the untimed warm-up populates the cache
   and the timed runs hit it. Record `cache: "enabled"`; `03-execute` verifies
   and re-measures it the same way. Its saving applies from the second run
   onward; say so in the record.

   A deselecting candidate (H15, H37) wins by running fewer tests, so it passes
   `--expect-total <count>`, records `removes_tests` with the number dropped and
   `removed_ids` with the node ids the `ids` command lists as `missing`, and
   reports the saving as time not spent on those tests, not as a faster suite.
   `02-plan` shows the count at the approval gate.

   This permits removal of passing outcomes only: the baseline's non-passing
   count must remain unchanged. Removing skipped or xfailed cases needs a
   separate selection policy; an expected total does not authorize it.

   A typing or parametrize hypothesis (H26-H32) saves no time by design: skip the
   timing. Run the suite once and the project's type checker over the test
   directory; it counts when both pass and the test count is unchanged (node ids
   may change by design). Record it
   with `kind: "hygiene"` and `median_delta` and `clears_noise` null.
4. **Safety gates** per `references/safety-gates.md`: the `valid` check
   above for every change; order independence (H17) and collection determinism
   (H18) for a change touching order, scope, or parallelism. A gate failure
   rejects the candidate and surfaces the prerequisite refactor as its own
   follow-up hypothesis. A parallelism candidate (H19) also runs 5-10 times,
   with the grouping (H20) and single-exec (H21) fixes from the same reference.
   H19 measures the control command (serial, as in step 3) and the same command
   plus `-n auto`, both recorded, the second as parallel; the no-xdist rule
   covers every other candidate.
5. **Discard** this hypothesis's scratch directory. The command removes only the
   directory step 1 created and leaves every other worktree and branch alone:

   ```console
   $ python3 <isolate.py> finish \
       --dir <dir>
   ```

   Confirm `git status --porcelain` matches its state before the phase.

## Step 3: Record

Write `benchmarks.json` in the shape `references/memory-schema.md` gives,
stamping each entry with `state.json`'s `env_token`, the `base_head`, and the
patch's `patch` path (relative to the memory directory), `patch_sha256` and
`files`. Keep the entries for ids this
run skipped (`--only` or a matching token) and replace those for ids it
benchmarked, `--force` included. Set `confidence` high only for serial, repeated runs with the delta above the
floor. Nothing in this phase touches the user's tree, history, or any remote. Update
`state.json` (`phase=benchmark`, `completed.benchmark=true`, the later
`completed` flags false).

## Step 4: Report

Emit the `01-benchmark` sections from `references/output-contract.md`. Write
the prose per `references/prose-rules.md`. Put each candidate under the
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

Close with an `ask-user-choice` panel offering to build the plan, re-benchmark a
subset, or stop. Without one, stop after the report and name the single next step in
one sentence, not a list of options.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
