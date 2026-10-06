---
name: pytest-optimizer-00-scan
description: >-
  Use when starting or re-baselining a pytest optimization pass by profiling
  tests and fixtures without editing the suite.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[test-path-or-marker] [--force] [--runs=N] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/00-scan/SKILL.md"
---

# 00-scan

Profile, detect, hypothesize. This phase never edits the suite. It writes only
JSON and one collection listing to the memory directory, plus one line in the
local git exclude file when it creates an in-tree memory directory.

`$ARGUMENTS` may scope the run to a path or marker, set `--runs=N` (baseline
sample count, default 5), `--force` to ignore the idempotency token, and
`--memory-dir` to override the memory location.

Arithmetic goes through `references/measure.py` (Python 3 standard
library). Run it by absolute path: `../../` is relative to this file.

## Step 1: Preflight

Read the project's own test command from `AGENTS.md`, `CLAUDE.md`,
`justfile`, `tox.ini`, or `pyproject.toml`, and record it; every later phase
reuses it. Substitute it wherever this file writes `pytest`.

If the project has no pytest suite, stop with the halted-run shape in
`references/output-contract.md`.

## Step 2: Resolve memory and check idempotency

Resolve the memory directory by the lookup order in
`references/memory-schema.md`; create it there if none exists. Save the
collection order:

```console
$ pytest --collect-only -q -p no:cacheprovider -p no:randomly
```

Write the node-id lines (unsorted) to `collection.txt`. Compute the idempotency
token defined in the schema with `measure.py token --head <HEAD sha>
--collection collection.txt --version <name>=<version> ...` (pytest and each
plugin). If `state.json` shows `scan` completed with an unchanged token and
`hypotheses.json` exists, report "already scanned" and stop, unless `--force`.

## Step 3: Detect capabilities

Probe the installed pytest and plugins against
`references/version-matrix.md` and write `capabilities.json`. Use only
available features below; fall back as the matrix directs.

## Step 4: Establish the baseline and noise band

Run the suite once untimed as a warm-up, then time `--runs` serial,
cache-disabled runs, appending each JSON line to a runs file in the memory
directory:

```console
$ python3 references/measure.py run \
    -- pytest -p no:cacheprovider -p no:randomly -q
```

`measure.py band <runs file>` prints the median, MAD, and noise band (floored at
the 50 ms trust floor), and exits 1 when any run fails or the test counts differ.
A failing baseline means the suite is red: stop and report it. Write the env
fingerprint, versions, capabilities, the band, and the passed/total counts to
`baseline.json`. See `references/durations-parsing.md`.

## Step 5: Profile slowest tests and fixtures

Capture per-phase timings, bucketed by the `when` token and de-duplicated by
`(nodeid, when)`:

```bash
pytest --durations=0 --durations-min=0.005 -p no:cacheprovider -p no:randomly
```

Rank slowest **test bodies** (`call`, H01) and slowest **fixture
setup/teardown** (H02). Note the attribution for a shared higher-scope fixture
billed to one nodeid (H03), and offer the opt-in timing plugin when precise
per-fixture cost is needed. Persist the timings to `baseline.json`.

## Step 6: Run the static detectors

Run every detector in `references/heuristic-catalog.md`, using
`references/fixture-analysis.md` for the fixture recipes and
`references/parametrize-convention.md` for the typing and parametrize
gaps (H26-H32). Emit H19 only when `time pytest --co -q` is a small share of
the baseline (H22 rules it out). Apply the `getfixturevalue` guard (H09)
before proposing any fixture deletion.

## Step 7: Emit hypotheses

Write `hypotheses.json`: one entry per firing detector with its heuristic id,
raw evidence, and prior risk/effort. Estimate no impact here; `01-benchmark`
measures it. Update `state.json` (`phase=scan`, `completed.scan=true`, token).

## Step 8: Report

Emit the `00-scan` sections from `references/output-contract.md`. Write the
prose per `references/prose-rules.md`. Report only measured numbers; project
no speedup before `01-benchmark`.

Close with an `ask-user-choice` panel offering to benchmark the hypotheses,
narrow scope, or stop. Without one, stop after the report and name the next
step in one sentence.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
