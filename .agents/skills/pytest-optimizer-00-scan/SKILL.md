---
name: pytest-optimizer-00-scan
description: >-
  Use when starting or re-baselining a pytest optimization pass by profiling
  tests and fixtures without editing the suite.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[test-path-or-marker] [--force] [--runs=N] [--hygiene] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/00-scan/SKILL.md"
---

# 00-scan

Profile, detect, hypothesize. This phase never edits the suite and never
installs anything into the user's environment without asking. It writes JSON and
one collection listing to the memory directory, run files under the git
directory (or the memory directory when that is unwritable), and one line in the
local git exclude file when it creates an in-tree memory directory. It does run
the project's tests, which can write files, and a project runner such as
`uv run` can update its own environment: Step 4 reports any change in the
working tree.

`$ARGUMENTS` may scope the run to a path or marker, set `--runs=N` (baseline
sample count, default 5), `--force` to ignore the idempotency token,
`--hygiene` to run the typing and parametrize detectors (H26-H32), and
`--memory-dir` to override the memory location. Those detectors rewrite test
signatures and case ids to one house convention, so they stay off unless asked.

Arithmetic goes through `references/measure.py` and the working-tree digest
through `references/isolate.py` (Python 3 standard library). Both paths
resolve from this skill's own directory, not the project's working directory:
resolve this file's directory, join each path, print the absolute paths once,
and write those literal paths in each command below where `<measure.py>` and
`<isolate.py>` appear.

## Step 1: Preflight

Read the project's own test command from `AGENTS.md`, `CLAUDE.md`,
`justfile`, `tox.ini`, or `pyproject.toml`. Append the scope from `$ARGUMENTS`
(a path or `-m <marker>`) to it, record the result as `test_command`, and
substitute it wherever this file writes `pytest`. Every later phase reuses
`test_command` unchanged, so baseline and candidates measure the same tests.

The measurement flags and how they attach to a wrapper are defined once in
`references/durations-parsing.md` ("Measurement command"); every command
below writes `pytest` for the resolved `test_command` plus those flags.

If the project has no pytest suite, or the test command cannot start (pytest is
not installed for it), stop with the halted-run shape in
`references/output-contract.md`: one clause naming that, no interpreter paths.

## Step 2: Resolve memory and check idempotency

Resolve the memory directory by the lookup order in
`references/memory-schema.md`; create it there if none exists. Save the
collection order:

```console
$ pytest --collect-only -q -p no:cacheprovider -p no:randomly
```

Write the node-id lines (unsorted) to `collection.txt`. Digest HEAD and every
dirty or untracked byte of the working tree:

```console
$ python3 <isolate.py> inputs \
    --cwd .
```

Compute the idempotency token defined in the schema with `measure.py token
--head <HEAD sha> --collection collection.txt --version <name>=<version> ...`
(pytest and each plugin) `--inputs-digest <digest> --command "<test_command>"`,
and store it in `state.json` as `env_token`, with `base_head` set to the same
`HEAD` sha, `inputs_digest`, `dirty` (the digest's flag), and `hygiene` set to
whether `--hygiene` was passed. A scan of a dirty tree is for inspection only:
`01-benchmark` and everything after it stop until the tree is clean and the scan
is re-run. If `state.json` shows
`scan` completed with an unchanged token and `hypotheses.json` exists, reply with one sentence saying the suite was already scanned and naming `--force` to rescan, then stop, unless `--force`
is passed or `--hygiene` differs from `state.json`'s `hygiene`.

Resolve `<runs-dir>` as `references/memory-schema.md` ("Run files") says
and create it. Run files live there, never in the working directory.

## Step 3: Detect capabilities

Probe the installed pytest and plugins against
`references/version-matrix.md` and write `capabilities.json`. Use only
available features below; fall back as the matrix directs. Install nothing into
the project's environment to widen the probe: an ephemeral `uv run --with <pkg>`
is fine, any other install needs the user's confirmation of the exact package and
environment, and without it the detector takes its fallback.

## Step 4: Establish the baseline and noise band

Run the command below once without the redirect as a warm-up; its `seconds` is
`t`. The scan costs about `(runs + 2) * t` in total: the warm-up, `--runs`
baseline runs, and the profile run; print that estimate before the first timed run. Above the default budget of 900 seconds
(the project's own limit, when its docs set one, replaces it), ask the user to
confirm or lower `--runs` (never below 3). Without an interactive question
tool, use `--runs=3` when that fits the budget and say so in the closing line;
when even three runs exceed it, stop before the first timed run and print the
estimate. Then time `--runs` measurement runs. Delete
`<runs-dir>/baseline-runs.jsonl` first, then append each JSON line to it; pass
`--timeout` of four times the warm-up's `seconds` so a hung suite is killed:

```console
$ python3 <measure.py> run \
    --timeout <seconds> \
    -- pytest -p no:cacheprovider -p no:randomly \
    >> <runs-dir>/baseline-runs.jsonl
```

Substitute `test_command` for `pytest`. Run `isolate.py inputs` again: when its
digest differs from Step 2's, the timed runs wrote files, so list them from
`git status --short` in the closing line. `measure.py band <runs-dir>/baseline-runs.jsonl`
prints the median, MAD, and noise band (floored at the larger of 50 ms and 1% of
the median). If `valid` is false, stop and report its `reason`: failed tests, a
timeout, too few runs, unavailable outcome counts and inconsistent counts are
distinct failures.
Remeasure unavailable counts only when the same runner and selection expose
an outcome summary; never fill them from a separate collection command.
Write the env fingerprint, versions,
capabilities, the measurement flags, the band, and the passed/total counts to
`baseline.json`. See
`references/durations-parsing.md`.

## Step 5: Profile slowest tests and fixtures

Capture per-phase timings, bucketed by the `when` token and de-duplicated by
`(nodeid, when)`:

```console
$ pytest --durations=0 --durations-min=0.005 -p no:cacheprovider -p no:randomly
```

Rank slowest **test bodies** (`call`, H01) and slowest **fixture
setup/teardown** (H02). Note the attribution for a shared higher-scope fixture
billed to one nodeid (H03), and offer the opt-in timing plugin when precise
per-fixture cost is needed. Persist the timings to `baseline.json`.

## Step 6: Run the static detectors

Run every detector in `references/heuristic-catalog.md`, using
`references/fixture-analysis.md` for the fixture recipes and
`references/parametrize-convention.md` for the typing and parametrize
gaps (H26-H32, only under `--hygiene`). Emit H19 only when `time pytest --co -q` is a small share of
the baseline (H22 rules it out). Apply the `getfixturevalue` guard (H09)
before proposing any fixture deletion.

## Step 7: Emit hypotheses

Write `hypotheses.json`: one entry per firing detector with its heuristic id,
raw evidence, and prior risk/effort. H01-H07 and H17/H18 are measurements and
gates: they appear in the report sections, never as entries. Estimate no impact here; `01-benchmark`
measures it. Update `state.json` (`phase=scan`, `completed.scan=true`, the later `completed`
flags false, token).

## Step 8: Report

Emit the `00-scan` sections from `references/output-contract.md`. Write the
prose per `references/prose-rules.md`. Report measured numbers. State no projected speedup or recoverable time before `01-benchmark`, and no verdict on whether a hypothesis can show a saving (a wide noise band is reported as a number, not as a prediction), and do not remark on the omission. Name time that no run attributed as unattributed; never call it startup or collection the suite cannot reduce, since nothing measured that. Reply in this shape, as plain text outside any
code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local
paths:

```text
✓ scan complete: baseline 12.5s, noise band 0.44s, 2 hypotheses

## Environment

- pytest 8.3.2 with xdist 3.6.1; deadfixtures not installed, so its check is skipped.

## Baseline

- Median 12.5s over 5 runs; trust floor 125ms (1% of the median).

## Slowest tests

- test_export_large spends 0.61s in one call (H01 slow test body, a measurement, not a hypothesis).

## Slowest fixtures

- db_session setup runs 3 times at 4.8s each, once per test (H02 slow fixture setup).

## Hypotheses

- H10 mis-scoped fixture: widen db_session to session scope, 4.8s of setup repeated per test.

Benchmarking the 2 hypotheses measures what each recovers.
```

Close with an `ask-user-choice` panel offering to benchmark the hypotheses,
narrow scope, or stop. Without one, stop after the report and name the next
step in one sentence.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
