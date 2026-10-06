---
name: pytest-optimizer
description: >-
  Use when pytest tests or fixtures are slow and you want them faster: speed
  up the suite with measured, safety-gated optimization.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[test-path-or-marker] [--phase=scan|benchmark|plan|execute] [--force] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/pytest-optimizer/SKILL.md"
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

Each phase is a separate skill that reads and writes durable JSON under the
resolved memory directory. Re-running resumes at the first incomplete phase.
After `03-execute`, re-scanning measures the new baseline; loop until no
candidate clears the rubric.

The phase skills set `disable-model-invocation`, so this skill cannot invoke
them. To run a phase, read its file and follow it:

- the `pytest-optimizer-00-scan` skill reads `AGENTS.md`/`CLAUDE.md` and prior `state.json`;
  writes `baseline.json`, `capabilities.json`, `collection.txt`,
  `hypotheses.json`.
- the `pytest-optimizer-01-benchmark` skill reads `baseline.json`, `hypotheses.json`; writes
  `benchmarks.json`.
- the `pytest-optimizer-02-plan` skill reads `benchmarks.json`, `baseline.json`; writes
  `plan.json`.
- the `pytest-optimizer-03-execute` skill reads `plan.json`, `baseline.json`; writes
  `execution-log.json` and commits.

## Step 1: Read-only preflight

Make no writes here; `00-scan` owns capability probing and creating the memory
directory.

1. Read the project's own test and quality-check commands from `AGENTS.md`,
   `CLAUDE.md`, `justfile`, `tox.ini`, and `pyproject.toml`. Never hardcode the
   runner: `pytest`, `uv run`, `tox`, `nox`, and `hatch` are all valid and the
   project declares which it uses.
2. Resolve the memory directory by the lookup order in
   `references/memory-schema.md`. If one exists, read `state.json` for the
   resume point.
3. Read the installed pytest version, for the plan only:

   ```console
   $ python3 -c "import pytest; print(pytest.__version__)"
   ```

If there is no pytest suite, stop with the halted-run shape in
`references/output-contract.md`.

## Orchestration Plan

Before any measurement or edit, present a plan and get approval.

1. **Enter plan mode.** In Claude Code call `EnterPlanMode`. In Cursor/Codex/Gemini
   use `/plan` or `Shift+Tab`. If plan mode is unavailable, the phase structure
   below still forces analysis before any write.
2. **The orchestration plan must state:**
   - the resolved test command and quality-check commands (Step 1);
   - the pytest version, and that `00-scan` will probe plugins and gate
     capabilities;
   - the resolved memory directory, or that `00-scan` will create it;
   - which phase the run starts at (fresh `00-scan`, or resume) and the scope
     (`$ARGUMENTS` path/marker, or the whole suite);
   - that suite edits happen only in `03-execute`, one commit per speedup, each
     verified green with unchanged test counts.
3. **Present the plan and wait for approval.** Let the user narrow scope, exclude
   risky heuristics, or cap the number of commits. Without an interactive
   session, stop after presenting the plan.
4. **Exit plan mode** before running any phase.

## Step 2: Run the phases

Read and follow each phase file in order, honoring `--phase` and resume state.
Pass along the test command and memory directory. `00-scan`, `01-benchmark`, and
`02-plan` never edit the user's working tree. Stop for the user's decision at
each phase's panel.

## Step 3: Report and decide whether to loop again

After `03-execute`, present the result per `references/output-contract.md`:
a hero block, the applied and skipped speedups with measured deltas, and an
`ask-user-choice` panel (re-scan for a second pass, scaffold the opt-in
cache/plugin, or stop). Without an interactive question tool, stop after the
report. Write the report per `references/prose-rules.md`.

## Opt-in scaffolds

When profiling shows it would help, offer (never impose) a project-owned helper:

- A timing plugin (`templates/pytest_optimizer_plugin.py`) that wraps
  `pytest_fixture_setup` to attribute setup cost to the individual fixture, which
  pytest core cannot do. It loads from the rootdir `conftest.py` only.
- A `config.cache` memoization snippet (`templates/conftest_cache_snippet.py`)
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
- **Dirty working tree:** `00-scan` may run. `01-benchmark` and `03-execute`
  refuse until the tree is clean, since a benchmark copy and a one-commit-per-
  speedup history both need a clean base. The memory directory does not count.

## References

- `references/scoring-rubric.md`: weighted rubric and the hard safety gate.
- `references/heuristic-catalog.md`: heuristic ids with
  detect/action/risk/effort.
- `references/version-matrix.md`: feature, min version, probe, fallback.
- `references/memory-schema.md`: memory location, file shapes, idempotency
  token, baseline-diff rule.
- `references/durations-parsing.md`: invoking and parsing `--durations`,
  phase bucketing, JUnit XML, the noise band.
- `references/measure.py`: median, MAD, noise band, outcome counts, order
  comparison, token, rubric arithmetic, memory-dir lookup.
- `references/fixture-analysis.md`: scope model and the
  unused/duplicate/mis-scope recipes.
- `references/safety-gates.md`: order independence, collection determinism,
  xdist preconditions.
- `references/parametrize-convention.md`: the typed NamedTuple + test_id
  convention and typed builtins.
- `references/output-contract.md`: the shared output shape.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
