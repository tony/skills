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
the project's tests, which can write files. A project runner can also update the
project environment first (`uv run` creates it or brings it up to date, per the
[uv project layout](https://docs.astral.sh/uv/concepts/projects/layout/) docs):
Step 4 reports any change in the working tree.

`$ARGUMENTS` may scope the run to a path or marker, set `--runs=N` (baseline
sample count, default 5), `--force` to ignore the idempotency token,
`--hygiene` to run the typing and parametrize detectors, and
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
`references/durations-parsing.md` ("Measurement command"). Every command
below writes `<test_command>` for the resolved command and `<flags>` for
`-p no:cacheprovider -p no:randomly`, plus `-n 0` when that section says to (an
xdist-configured suite).

The static detectors search with `rg` (ripgrep). Run `rg --version`; when it is
missing, stop with the halted-run shape naming ripgrep as the missing
prerequisite, since a scan without it would report no hypotheses as if the suite
were clean.

If the project has no pytest suite, or the test command cannot start (pytest is
not installed for it), stop with the halted-run shape in
`references/output-contract.md`: one clause naming that, no interpreter paths.

## Step 2: Resolve memory and check idempotency

Resolve the memory directory by the lookup order in
`references/memory-schema.md`; create it there if none exists. Save the
collection order:

```console
$ <test_command> --collect-only -q <flags>
```

Write the node-id lines (unsorted) to `collection.txt`. Digest HEAD and every
dirty or untracked byte of the working tree:

```console
$ python3 <isolate.py> inputs \
    --cwd .
```

Compute the idempotency token defined in the schema with `measure.py token
--head <HEAD sha> --collection collection.txt --version <name>=<version> ...`
(pytest and each plugin) `--inputs-digest <digest> --command "<test_command>"`.
Step 7 stores it in `state.json` as `env_token`, with `base_head` set to the same
`HEAD` sha, `inputs_digest`, `dirty` (the digest's flag), and `hygiene` set to
whether `--hygiene` was passed. A dirty tree makes the scan inspection-only (the
schema's "Idempotency token" holds the rule). Then ask whether the recorded scan
still stands:

```console
$ python3 <measure.py> state \
    unchanged <memory-dir>/state.json \
    --token <token> \
    --hygiene <true|false> \
    --require hypotheses.json
```

When `unchanged` is true and `--force` is not passed, reply with one sentence
saying the suite was already scanned and naming `--force` to rescan, then stop.

Resolve `<runs-dir>` as `references/memory-schema.md` ("Run files") says
and create it. Run files live there, never in the working directory.

## Step 3: Detect capabilities

Probe the installed pytest and plugins against
`references/version-matrix.md` and write `capabilities.json`, one probe per
call:

```console
$ python3 <measure.py> state \
    update <memory-dir>/capabilities.json \
    --set 'durations_min=true'
```

Use only
available features below; fall back as the matrix directs. Install nothing into
the project's environment to widen the probe: an ephemeral `uv run --with <pkg>`
is fine, any other install needs the user's confirmation of the exact package and
environment, and without it the detector takes its fallback.

## Step 4: Establish the baseline and noise band

Run the command below once without the redirect as a warm-up; its `seconds` is
`t`. Price the scan (the warm-up, `--runs` baseline runs, and the profile run)
and print its `estimate` before the first timed run; the project's own limit,
when its docs set one, replaces the 900-second default:

```console
$ python3 <measure.py> budget \
    --phase scan \
    --seconds <t> \
    --runs <N>
```

When `over` is true, ask the user to confirm or lower `--runs` (never below 3).
Without an interactive question tool, use `--runs=3` when that budget call says
it fits and say so in the closing line; when even three runs exceed it, stop
before the first timed run and print the estimate. Then time `--runs`
measurement runs. Delete `<runs-dir>/baseline-runs.jsonl` first, then append each
JSON line to it; pass the `timeout` the budget call printed as `--timeout` so a
hung suite is killed:

```console
$ python3 <measure.py> run \
    --timeout <seconds> \
    -- <test_command> <flags> \
    >> <runs-dir>/baseline-runs.jsonl
```

Run `isolate.py inputs` again: when its
digest differs from Step 2's, the timed runs wrote files, so list them from
`git status --short` in the closing line. `measure.py baseline` computes the
median, MAD and noise band (floored at the larger of 50 ms and 1% of the
median) and writes `baseline.json` with the environment, versions, capabilities,
measurement flags and passed/total counts (the shape and arguments are in
`references/memory-schema.md`):

```console
$ python3 <measure.py> baseline \
    <runs-dir>/baseline-runs.jsonl \
    --out <memory-dir>/baseline.json \
    --test-command "<test_command>" \
    --pytest-version <version> \
    --plugin <name>=<version> \
    --flag=-p \
    --flag=no:cacheprovider \
    --flag=-p \
    --flag=no:randomly \
    --capabilities <memory-dir>/capabilities.json
```

Repeat `--plugin` for each installed plugin and `--flag` for each measurement
flag, `-n 0` included when it applies.

If it exits 1, nothing is written: stop and report its `reason`. Failed tests, a
timeout, too few runs, unavailable outcome counts and inconsistent counts are
distinct failures. Remeasure unavailable counts only when the same runner and
selection expose an outcome summary; never fill them from a separate collection
command. See `references/durations-parsing.md`.

## Step 5: Profile slowest tests and fixtures

Capture per-phase timings into a run file:

```console
$ <test_command> --durations=0 --durations-min=0.005 <flags> \
    > <runs-dir>/durations.txt
```

Store them by running the Step 4 `baseline` command again with `--durations
<runs-dir>/durations.txt` added; it keeps the other fields and records one row per
`(nodeid, phase)`. Rank the slowest test bodies (`call` rows) and the slowest
fixture setup and teardown rows. Note the attribution for a shared higher-scope
fixture billed to one nodeid, and offer the opt-in timing plugin when precise
per-fixture cost is needed.

## Step 6: Run the static detectors

Run every detector in `references/heuristic-catalog.md`, using
`references/fixture-analysis.md` for the fixture recipes and
`references/parametrize-convention.md` for the typing and parametrize
gaps (only under `--hygiene`). Emit the parallelism candidate only when
`time <test_command> --co -q` is a small share of the baseline (the
collection-time check rules it out). Apply the `getfixturevalue` guard before
proposing any fixture deletion.

## Step 7: Emit hypotheses

Write `hypotheses.json`: one entry per firing detector with its heuristic id,
raw evidence, and prior risk/effort. Take each `id` and write each entry through
the scripts, since the id derives from content:

```console
$ python3 <measure.py> hyp-id \
    --heuristic <Hnn> \
    --file <each target file> \
    --evidence "<raw evidence>"
```

```console
$ python3 <measure.py> record <memory-dir>/hypotheses.json \
    --id <id> \
    --set 'heuristic="<Hnn>"' \
    --set 'evidence="<raw evidence>"' \
    --set 'est_risk="<low|medium|high>"' \
    --set 'est_effort="<trivial|small|large>"' \
    --set 'status="open"'
```

The measurement heuristics and the safety gates appear in the report sections,
never as entries.
Estimate no impact here; `01-benchmark` measures it. Then record the scan, which
also clears the later phases' flags:

```console
$ python3 <measure.py> state \
    complete <memory-dir>/state.json \
    --phase scan \
    --set 'env_token="<token>"' \
    --set 'base_head="<HEAD sha>"' \
    --set 'inputs_digest="<digest>"' \
    --set 'dirty=<true|false>' \
    --set 'hygiene=<true|false>'
```

## Step 8: Report

Emit the `00-scan` sections from `references/output-contract.md`. Write the
prose per `references/prose-rules.md`. Report measured numbers. State no projected speedup or recoverable time before `01-benchmark`, and no verdict on whether a hypothesis can show a saving (a wide noise band is reported as a number, not as a prediction), and do not remark on the omission. Name time that no run attributed as unattributed; never call it startup or collection the suite cannot reduce, since nothing measured that. Reply in this shape, as plain text outside any
code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local
paths:

```text
✓ scan complete: baseline 12.5s, noise band 0.44s, 2 hypotheses

## Environment

- pytest 9.1.1 with xdist 3.8.0; deadfixtures not installed, so its check is skipped.

## Baseline

- Median 12.5s over 5 runs; trust floor 125ms (1% of the median).

## Slowest tests

- test_export_large spends 0.61s in one call (H01 slow test body, a measurement, not a hypothesis).

## Slowest fixtures

- db_session setup runs 3 times at 4.8s each, once per test (H02 slow fixture setup).

## Hypotheses

- H10 mis-scoped fixture: widen db_session to session scope, 4.8s of setup repeated per test.
- H33 fixed sleep in test_report: time.sleep(0.02) in the test body.

Benchmarking the 2 hypotheses measures what each recovers.
```

After the last section write at most one closing sentence (files the timed runs
wrote, a dirty tree, a lowered run count), then an `ask-user-choice` panel
offering to benchmark the hypotheses, narrow scope, or stop. Without a question
tool, print those options as a plain list and stop, as the output contract's
next-step rule says.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
