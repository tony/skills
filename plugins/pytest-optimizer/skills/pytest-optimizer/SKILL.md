---
name: pytest-optimizer
description: "Use when pytest tests or fixtures are slow and you want them faster: speed up the suite with measured, safety-gated optimization."
user-invocable: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[test-path-or-marker] [--phase=scan|benchmark|plan|execute] [--force] [--memory-dir=<path>]"
---

# pytest-optimizer

Profile a pytest suite, find safe speedups, and apply each as its own verified
commit through a resumable, idempotent four-phase loop.

Measure before you mutate, and prove a speedup against the project's own timing
noise before you trust it. A change whose measured saving falls inside the noise
band, whose run exits non-zero, or whose test count changes is never committed.

`$ARGUMENTS` may name a test path or marker to scope the run, a `--phase` to jump
to, `--force` to ignore idempotency tokens and re-run, and `--memory-dir` to
override where durable state is written.

## The loop

```
00-scan  ->  01-benchmark  ->  02-plan  ->  03-execute  ->  (re-scan)
```

Each phase reads and writes durable JSON under the resolved memory directory;
re-running resumes at the first incomplete phase. After `03-execute`, re-scan and
loop until no candidate clears the rubric.

The phase skills set `disable-model-invocation`, so this skill cannot invoke
them. To run a phase, read its file and follow it:

- `../00-scan/SKILL.md` reads `AGENTS.md`/`CLAUDE.md` and prior `state.json`;
  writes `baseline.json`, `capabilities.json`, `collection.txt`,
  `hypotheses.json`.
- `../01-benchmark/SKILL.md` reads `baseline.json`, `hypotheses.json`; writes
  `benchmarks.json`.
- `../02-plan/SKILL.md` reads `benchmarks.json`, `baseline.json`; writes
  `plan.json`.
- `../03-execute/SKILL.md` reads `plan.json`, `baseline.json`; writes
  `execution-log.json` and commits.

## Step 1: Read-only preflight

Make no writes here; `00-scan` owns capability probing and creating the memory
directory.

1. Read the project's own test and quality-check commands from `AGENTS.md`,
   `CLAUDE.md`, `justfile`, `tox.ini`, and `pyproject.toml`; the runner
   (`pytest`, `uv run`, `tox`, `nox`, `hatch`) is the project's choice.
2. Resolve the memory directory by the lookup order in
   `../../references/memory-schema.md`. If one exists, read `state.json` for the
   resume point.
3. Read the installed pytest version, for the plan only, through the project's
   runner so the project environment answers, not the system Python:

   ```console
   $ pytest --version
   ```

   Prefix the project's runner when it has one (`uv run pytest --version`,
   `tox -e py -- --version`).

If there is no pytest suite, stop with the halted-run shape in
`../../references/output-contract.md`. A saving is a measured number: when
nothing was run, state no projected timing, and call a scope change a
hypothesis to benchmark, not a fix.

## Orchestration Plan

Before any measurement or edit, present a plan and get approval.

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present a plan stating:

- the resolved test and quality-check commands (Step 1);
- the pytest version, and that `00-scan` will probe plugins and gate
  capabilities;
- the resolved memory directory, or that `00-scan` will create it;
- the starting phase (fresh `00-scan`, or resume) and the scope (`$ARGUMENTS`
  path or marker, or the whole suite);
- that suite edits happen only in `03-execute`, one commit per speedup, each
  verified green with unchanged test counts.

Let the user narrow scope, exclude risky heuristics, or cap the commit count.
Wait for approval, then exit plan mode before running any phase. Without plan
mode, the phase structure still forces analysis before any write; without an
interactive session, stop after presenting the plan.

## Step 2: Run the phases

Read and follow each phase file in order, honoring `--phase` and resume state.
Pass along the test command and memory directory. `00-scan`, `01-benchmark`, and
`02-plan` never edit the user's working tree. Stop for the user's decision at
each phase's panel.

## Step 3: Report and decide whether to loop again

After `03-execute`, present the result per `../../references/output-contract.md`
and write it per `../../references/prose-rules.md`, then offer a re-scan, the
opt-in scaffolds, or stop. Without an interactive question tool, stop after the
report.

## Opt-in scaffolds

When profiling shows it would help, offer (never impose) a project-owned helper:

- A timing plugin (`../../templates/pytest_optimizer_plugin.py`) that wraps
  `pytest_fixture_setup` to attribute setup cost to the individual fixture, which
  pytest core cannot do. It loads from the rootdir `conftest.py` only.
- A `config.cache` memoization snippet (`../../templates/conftest_cache_snippet.py`)
  with an invalidation token and an xdist write-guard, for expensive build
  artifacts recomputed every run. It raises until `INPUTS` is set.

Generate only on explicit confirmation. The output is untracked; exclude it per
the memory-schema reference unless the user chooses to commit it.

## Graceful degradation

- **Old pytest:** gate features via the version matrix; widen `k` when duration
  precision is coarser (pre-6.0 used `time.time()`).
- **No xdist, randomly, or deadfixtures:** fall back to serial runs, manual
  reversed-order isolation checks, and the built-in `--fixtures` vs
  `--fixtures-per-test` diff.
- **Dirty working tree:** `00-scan` may run; `01-benchmark` and `03-execute`
  refuse until it is clean. The memory directory does not count.

## References

- `../../references/scoring-rubric.md`: weighted rubric and the hard safety gate.
- `../../references/heuristic-catalog.md`: heuristic ids with
  detect/action/risk/effort.
- `../../references/version-matrix.md`: feature, min version, probe, fallback.
- `../../references/memory-schema.md`: memory location, file shapes, idempotency
  token, baseline-diff rule.
- `../../references/durations-parsing.md`: invoking and parsing `--durations`,
  phase bucketing, JUnit XML, the noise band.
- `../../scripts/measure.py`: median, MAD, noise band, outcome counts, order
  comparison, token, rubric arithmetic, memory-dir lookup.
- `../../references/fixture-analysis.md`: scope model and the
  unused/duplicate/mis-scope recipes.
- `../../references/safety-gates.md`: order independence, collection determinism,
  xdist preconditions.
- `../../references/parametrize-convention.md`: the typed NamedTuple + test_id
  convention and typed builtins.
- `../../references/output-contract.md`: the shared output shape.
