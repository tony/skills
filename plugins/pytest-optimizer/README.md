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

## Why four skills instead of one loop

A single autonomous loop cannot be re-entered safely on failure. Each phase
reads and writes a durable JSON file under `.pytest-optimizer/`, keeping the
pipeline:

- **Idempotent** — Re-running a phase is a no-op if inputs are unchanged.
- **Resumable** — `03-execute` checkpoints after every commit.
- **Auditable** — The plan is a reviewable artifact before any code changes.

## What it looks for

The detection rules are in `references/heuristic-catalog.md`:

- Slowest test bodies and fixture setup, ranked from `--durations` rows.
- Unused, duplicate, and mis-scoped fixtures, with a `getfixturevalue` guard.
- Duplicate tests and loops that belong in one parametrized track.
- Safe parallelism, gated on order independence and deterministic collection.
- Untyped tests and fixtures, and untyped `parametrize` data.
- Opt-in project-owned helpers: a per-fixture timing plugin and a
  `config.cache` memoization snippet.

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

- `skills/00-scan`, `01-benchmark`, `02-plan`, `03-execute` — The four phase skills.
- `skills/pytest-optimizer/SKILL.md` — Orchestrator with planning and
  degradation.
- `references/` — Recipes, schemas, rubric, and capabilities.
- `templates/` — Opt-in scaffolds (timing plugin, cache snippet) and the commit message template.

## Scope

The pipeline is runner-agnostic, but the heuristics are pytest-specific
(degrading gracefully down to pytest 6.x).
