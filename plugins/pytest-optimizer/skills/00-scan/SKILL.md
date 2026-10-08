---
name: 00-scan
description: "Use when starting or re-baselining a pytest optimization pass by profiling tests and fixtures without editing the suite."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
argument-hint: "[test-path-or-marker] [--force] [--runs=N] [--hygiene] [--memory-dir=<path>]"
disable-model-invocation: true
---

# 00-scan

Profile, detect, hypothesize. This phase never edits the suite and never
installs anything into the user's environment without asking. It writes only
JSON and one collection listing to the memory directory, run files under the git
directory (or the memory directory when that is unwritable), and one line in the
local git exclude file when it creates an in-tree memory directory.

`$ARGUMENTS` may scope the run to a path or marker, set `--runs=N` (baseline
sample count, default 5), `--force` to ignore the idempotency token,
`--hygiene` to run the typing and parametrize detectors (H26-H32), and
`--memory-dir` to override the memory location. Those detectors rewrite test
signatures and case ids to one house convention, so they stay off unless asked.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`../../scripts/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Preflight

Read the project's own test command from `AGENTS.md`, `CLAUDE.md`,
`justfile`, `tox.ini`, or `pyproject.toml`. Append the scope from `$ARGUMENTS`
(a path or `-m <marker>`) to it, record the result as `test_command`, and
substitute it wherever this file writes `pytest`. Every later phase reuses
`test_command` unchanged, so baseline and candidates measure the same tests.

Measurement flags (`-p no:cacheprovider -p no:randomly -q`) go straight onto a
command that runs pytest itself (`pytest`, `uv run pytest`, `python -m pytest`).
For a wrapper (`tox -e py`, `nox -s tests`, `make test`), pass them through the
wrapper's own separator (`tox -e py -- <flags>`); when the wrapper has none, run
it without them and record that in `baseline.json`.

If the project has no pytest suite, or the test command cannot start (pytest is
not installed for it), stop with the halted-run shape in
`../../references/output-contract.md`: one clause naming that, no interpreter paths.

## Step 2: Resolve memory and check idempotency

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`; create it there if none exists. Save the
collection order:

```console
$ pytest --collect-only -q -p no:cacheprovider -p no:randomly
```

Write the node-id lines (unsorted) to `collection.txt`. Compute the idempotency
token defined in the schema with `measure.py token --head <HEAD sha>
--collection collection.txt --version <name>=<version> ...` (pytest and each
plugin), and store it in `state.json` as `env_token`, with `base_head` set to the same
`HEAD` sha (`03-execute` resumes against it) and `hygiene` set to whether `--hygiene`
was passed. If `state.json` shows
`scan` completed with an unchanged token and `hypotheses.json` exists, reply with one sentence saying the suite was already scanned and naming `--force` to rescan, then stop, unless `--force`
is passed or `--hygiene` differs from `state.json`'s `hygiene`.

Resolve `<runs-dir>` as `../../references/memory-schema.md` ("Run files") says
and create it. Run files live there, never in the working directory.

## Step 3: Detect capabilities

Probe the installed pytest and plugins against
`../../references/version-matrix.md` and write `capabilities.json`. Use only
available features below; fall back as the matrix directs. Install nothing into
the project's environment to widen the probe: an ephemeral `uv run --with <pkg>`
is fine, any other install needs the user's confirmation of the exact package and
environment, and without it the detector takes its fallback.

## Step 4: Establish the baseline and noise band

Run the command below once without the redirect as a warm-up; its `seconds` is
`t`. The scan costs about `(runs + 2) * t` in total: the warm-up, `--runs`
baseline runs, and the profile run; print that estimate before the first timed run. Above the default budget of 900 seconds
(the project's own limit, when its docs set one, replaces it), ask the user to
confirm or lower `--runs` (never below 3); without an interactive question tool, lower
`--runs` to 3 and say so in the closing line. Then time `--runs` serial,
cache-disabled runs. Delete `<runs-dir>/baseline-runs.jsonl` first, then append
each JSON line to it:

```console
$ python3 <measure.py> run \
    -- pytest -p no:cacheprovider -p no:randomly -q \
    >> <runs-dir>/baseline-runs.jsonl
```

Substitute `test_command` for `pytest`. `measure.py band <runs-dir>/baseline-runs.jsonl`
prints the median, MAD, and noise band (floored at the larger of 50 ms and 1% of
the median), and exits 1 when any run fails or the test counts differ. A failing baseline means
the suite is red: stop and report it. Write the env fingerprint, versions,
capabilities, the band, and the passed/total counts to `baseline.json`. See
`../../references/durations-parsing.md`.

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

Run every detector in `../../references/heuristic-catalog.md`, using
`../../references/fixture-analysis.md` for the fixture recipes and
`../../references/parametrize-convention.md` for the typing and parametrize
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

Emit the `00-scan` sections from `../../references/output-contract.md`. Write the
prose per `../../references/prose-rules.md`. Report measured numbers. State no projected speedup or recoverable time before `01-benchmark`, and do not remark on the omission. Reply in this shape, as plain text outside any
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

Close with an `AskUserQuestion` panel offering to benchmark the hypotheses,
narrow scope, or stop. Without one, stop after the report and name the next
step in one sentence.
