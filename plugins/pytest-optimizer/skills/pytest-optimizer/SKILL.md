---
name: pytest-optimizer
description: "Use when a pytest suite or its fixtures are slow and need measured, safety-gated optimization across the full pipeline."
user-invocable: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
argument-hint: "[test-path-or-marker] [--phase=scan|benchmark|plan|execute] [--force] [--memory-dir=<path>]"
---

# pytest-optimizer

Profile a pytest suite, find safe speedups, and apply each as its own verified
commit through a resumable, idempotent four-phase loop.

Measure before you mutate, and prove a speedup against the project's own timing
noise before you trust it. A change whose measured saving falls inside the noise
band is never committed.

`$ARGUMENTS` may name a test path or marker to scope the run, a `--phase` to jump
to, `--force` to ignore idempotency tokens and re-run, and `--memory-dir` to
override where durable state is written.

## The loop

```
00-scan  ->  01-benchmark  ->  02-plan  ->  03-execute  ->  (re-scan)
```

Each phase is a separate skill that reads and writes durable JSON under the
resolved memory directory. Re-running resumes at the first incomplete phase.
After `03-execute`, re-scanning measures the new baseline; loop until no
candidate clears the rubric.

- `/pytest-optimizer:00-scan` reads `AGENTS.md`/`CLAUDE.md` and prior
  `state.json`; writes `baseline.json`, `capabilities.json`, `hypotheses.json`.
- `/pytest-optimizer:01-benchmark` reads `baseline.json`, `hypotheses.json`;
  writes `benchmarks.json`.
- `/pytest-optimizer:02-plan` reads `benchmarks.json`, `baseline.json`; writes
  `plan.json`.
- `/pytest-optimizer:03-execute` reads `plan.json`, `baseline.json`; writes
  `execution-log.json` and commits.

## Step 1: Detect preferred tools and the project test command

Read the project's own test and quality-check commands. Never hardcode the
runner: `pytest`, `uv run`, `tox`, `nox`, and `hatch` are all valid and the
project declares which it uses.

```bash
for tool in rg ag fd jq uv uvx; do command -v "$tool" >/dev/null 2>&1 && echo "$tool:available" || echo "$tool:missing"; done
```

Read `AGENTS.md`, `CLAUDE.md`, `justfile`, `tox.ini`, and `pyproject.toml` for the
commands that run the suite, the formatter, the linter, and the type checker.
Record the test command verbatim; every phase reuses it.

## Step 2: Detect pytest capabilities

Run the detection procedure in `../../references/version-matrix.md` once and
write the resolved matrix to `capabilities.json`, so later phases use only
features that exist.

## Step 3: Resolve the memory directory

Follow `../../references/memory-schema.md`: prefer `.pytest-optimizer/` at the
repo root, excluded through the repo's local git exclude file so the working tree
stays clean. Fall back to the XDG cache path when the tree is read-only or the
user declines an in-tree directory. Record the path in `state.json`.

## Orchestration Plan

Before any measurement or edit, present a plan and get approval.

1. **Enter plan mode.** In Claude Code call `EnterPlanMode`. In Cursor/Codex/Gemini
   use `/plan` or `Shift+Tab`. If plan mode is unavailable, the phase structure
   below still forces analysis before any write.
2. **The orchestration plan must state:**
   - the resolved test command and quality-check commands (Step 1);
   - the detected pytest and plugin versions and which capabilities are gated off
     (Step 2);
   - the resolved memory directory;
   - which phase the run starts at (fresh `00-scan`, or resume) and the scope
     (`$ARGUMENTS` path/marker, or the whole suite);
   - that suite edits happen only in `03-execute`, one commit per speedup, each
     verified green.
3. **Present the plan and wait for approval.** Let the user narrow scope, exclude
   risky heuristics, or cap the number of commits.
4. **Exit plan mode** before running any phase.

## Step 4: Run the phases

Run the four skills in order, honoring `--phase` and resume state. Each skill
carries its own procedure; this skill passes along the test command,
capabilities, and memory directory. Within `00-scan`, `01-benchmark`, and
`02-plan`, never edit the user's working tree.

## Step 5: Report and decide whether to loop again

After `03-execute`, re-measure total wall-time against `baseline.json` and present
the result per `../../references/output-contract.md`: a hero block, the
applied and skipped speedups with measured deltas, and an `AskUserQuestion`
panel (re-scan for a second pass, scaffold the opt-in cache/plugin, or stop).
Write the report per `../../references/prose-rules.md`.

## Opt-in scaffolds

When profiling shows it would help, offer (never impose) a project-owned helper:

- A timing plugin (`../../templates/pytest_optimizer_plugin.py`) that wraps
  `pytest_fixture_setup` to attribute setup cost to the individual fixture, which
  pytest core cannot do.
- A `config.cache` memoization snippet (`../../templates/conftest_cache_snippet.py`)
  with an invalidation token and an xdist write-guard, for expensive build
  artifacts recomputed every run.

Generate only on explicit confirmation. The output is untracked; exclude it per
the memory-schema reference unless the user chooses to commit it.

## Graceful degradation

- **Old pytest:** gate features via the version matrix; widen the noise band when
  duration precision is coarser (pre-6.0 used `time.time()`).
- **No xdist, randomly, or deadfixtures:** fall back to serial runs, manual
  reversed-order isolation checks, and the built-in `--fixtures` vs
  `--fixtures-per-test` diff.
- **Dirty working tree:** `00-scan` may run. `01-benchmark` and `03-execute`
  refuse until the tree is clean, since a benchmark copy and a one-commit-per-
  speedup history both need a clean base. The memory directory does not count.

## References

- `../../references/scoring-rubric.md`: weighted rubric and the hard safety gate.
- `../../references/heuristic-catalog.md`: heuristic ids with
  detect/action/risk/effort.
- `../../references/version-matrix.md`: feature, min version, probe, fallback.
- `../../references/memory-schema.md`: memory location, file shapes, idempotency
  token, baseline-diff rule.
- `../../references/durations-parsing.md`: invoking and parsing `--durations`,
  phase bucketing, JUnit XML, the noise band.
- `../../references/fixture-analysis.md`: scope model and the
  unused/duplicate/mis-scope recipes.
- `../../references/safety-gates.md`: order independence, collection determinism,
  xdist preconditions.
- `../../references/parametrize-convention.md`: the typed NamedTuple + test_id
  convention and typed builtins.
- `../../references/output-contract.md`: the shared output shape.
