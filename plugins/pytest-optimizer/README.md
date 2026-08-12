# pytest-optimizer

Profile and optimize pytest suites. Ranks and applies safe speedups as
verified, independent commits.

It runs as a **resumable four-phase pipeline**. Measurement and mutation are
separated on purpose: you can re-run any phase without redoing the previous
one, and the suite is never edited until a speedup has been measured against
the project's own timing noise and has cleared a safety gate.

```
00-scan  ->  01-benchmark  ->  02-plan  ->  03-execute
profile      prove each        rank by       apply each speedup
+ detect     hypothesis vs      the safety    as a separate commit,
+ hypothesize  noise band       rubric        verify green, resume
```

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install pytest-optimizer@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add pytest-optimizer@skills
```

The skills below use Claude Code's leading slash. Codex uses the same names
without it (`pytest-optimizer:…`).

## Why four commands instead of one loop

A single autonomous loop cannot be re-entered safely on failure. Each phase
reads and writes a durable JSON file under `.pytest-optimizer/`, keeping the
pipeline:

- **Idempotent** — Re-running a phase is a no-op if inputs are unchanged.
- **Resumable** — `03-execute` checkpoints after every commit.
- **Auditable** — The plan is a reviewable artifact before any code changes.

## What it looks for

The detection rules map to specific optimization goals (defined in
`references/heuristic-catalog.md`):

| Goal | Approach |
|------|----------|
| 1. Slowest tests + root cause | Rank `--durations` rows for `call` phase; attribute in-test costs. |
| 2. Slowest fixtures + root cause | Rank `setup`/`teardown` rows; optionally use `pytest11` timing plugin. |
| 3. Consolidate tracks | Merge duplicate test loops/fixtures into a parametrized track. |
| 4. Detect unused fixtures | Diff defined fixtures vs used closures with a `getfixturevalue` guard. |
| 5. Proper fixture scope | Analyze setup counts to flag expensive function-scoped fixtures. |
| 6. Safe speedups | Score candidates with a weighted rubric; enforce a hard safety gate. |
| 7. Try ideas + report | Prove hypotheses against noise bands in throwaway copies (`01-benchmark`). |
| 8. Apply speedups safely | Commit changes independently with verification (`03-execute`). |
| 9. Typings | Detect untyped tests/fixtures and legacy `tmpdir`; add types. |
| 10. Typed parametrize | Migrate to `class XFixture(t.NamedTuple)` for test params. |
| 11. Project-owned cache | Scaffold a `pytest11` plugin and `config.cache` memoization. |

## The safety rubric

Candidates are ranked and gated (see `references/scoring-rubric.md`):

| Dimension | Weight | Meaning |
|-----------|-------:|---------|
| safety | 0.35 | **Hard gate: score < 0.4 is dropped.** Inverse of correctness risk. |
| impact | 0.30 | Measured wall-clock delta vs the noise band. (Within-noise scores 0.) |
| effort | 0.15 | Inverse of refactor cost. |
| confidence | 0.12 | Quality of timing evidence (e.g., serial, repeated, above noise floor). |
| reversibility | 0.08 | How cleanly the change is undone if green-verify fails. |

## Skills

| Skill | Phase | Writes |
|---------|-------|--------|
| `/pytest-optimizer:00-scan` | Profile, detect, hypothesize (plan-mode gated) | `baseline.json`, `capabilities.json`, `hypotheses.json` |
| `/pytest-optimizer:01-benchmark` | Prove each hypothesis vs the noise band | `benchmarks.json` |
| `/pytest-optimizer:02-plan` | Rank into a commit plan (plan-mode gated) | `plan.json` |
| `/pytest-optimizer:03-execute` | Apply each speedup as a commit, verify, resume | `execution-log.json` |

Use `pytest-optimizer` as an orchestrator for conversational phrases like
"speed up my tests".

## Memory

Durable state lives in `.pytest-optimizer/` at the repo root. It falls back
to XDG cache dirs if the tree is read-only. See `references/memory-schema.md`.

## Prerequisites

- A git repository with a pytest suite.
- Test commands configured via `AGENTS.md` or `CLAUDE.md`.
- Optional auto-detected plugins: `pytest-xdist`, `pytest-randomly`,
  `pytest-deadfixtures` (via `uvx`), `pytest-timeout`.

## Component reference

- `commands/` — The four phase commands.
- `skills/pytest-optimizer/SKILL.md` — Orchestrator with planning and
  degradation.
- `references/` — Recipes, schemas, rubric, and capabilities.
- `templates/` — Opt-in scaffolds (timing plugins, caches, gitignores).

## Scope

The pipeline is runner-agnostic, but the heuristics are pytest-specific
(degrading gracefully down to pytest 6.x).
