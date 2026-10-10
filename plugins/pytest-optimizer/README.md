# pytest-optimizer

Profile and optimize pytest suites. Ranks and applies safe speedups as
verified, independent commits.

It runs as a resumable four-phase pipeline. Measurement and mutation are
separated on purpose: you can re-run any phase without redoing the previous
one, and the suite is never edited until a speedup has been measured against
the project's own timing noise and has cleared a safety gate.

```
00-scan  ->  01-benchmark  ->  02-plan  ->  03-execute
profile      prove each        rank by       apply each speedup
+ detect     hypothesis vs      the safety    as a separate commit
+ hypothesize  noise band       rubric        on a new branch
```

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install pytest-optimizer --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install pytest-optimizer@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add pytest-optimizer@skills
```

Claude Code uses a leading slash (`/pytest-optimizer:…`). Codex omits it (`pytest-optimizer:…`).

## Why four skills instead of one loop

A single autonomous loop cannot be re-entered safely on failure. Each phase
reads and writes a durable JSON file under `.pytest-optimizer/`, keeping the
pipeline:

- Idempotent: Re-running a phase is a no-op if inputs are unchanged.
- Resumable: `03-execute` checkpoints after every commit and, on resume, checks that its result branch holds only its own commits.
- Auditable: The plan is a reviewable artifact before any code changes.

## What execution touches

`03-execute` never edits your checkout, index or branches. It cuts a new
branch from the commit the scan measured, applies each benchmarked patch in a
scratch worktree it owns, verifies and commits there, and discards a failed item
inside that worktree only. It ends by naming the branch and the command that
merges it, and does not merge or push:

```console
$ git merge --ff-only pytest-optimizer/<run-id>
```

Your checkout can stay dirty and keep changing meanwhile. The worktree is a Git
boundary, not a sandbox: a project hook or an absolute path in a test can still
write elsewhere. `00-scan` runs the project's tests in your tree, so it
compares the working tree before and after and reports files the tests wrote.

## What it looks for

The detection rules are in `references/heuristic-catalog.md`:

- Slowest test bodies and fixture setup, ranked from `--durations` rows.
- Unused, duplicate, and mis-scoped fixtures, with a `getfixturevalue` guard.
- Duplicated helpers across sibling conftests.
- Safe parallelism, gated on order independence and deterministic collection.
- With `--hygiene`, untyped tests and fixtures and untyped `parametrize` data, planned as hygiene items that save no time. Off by default: they rewrite test signatures and ids.
- Opt-in project-owned helpers: a per-fixture timing plugin and a
  `config.cache` memoization snippet.

## The safety rubric

Candidates are ranked and gated (see `references/scoring-rubric.md`):

| Dimension | Weight | Meaning |
|-----------|-------:|---------|
| safety | 0.35 | Hard gate: a score under 0.4 is dropped. Inverse of correctness risk. |
| impact | 0.30 | Measured wall-clock delta vs the noise band, as a share of the baseline. (Within-noise scores 0.) |
| effort | 0.15 | Inverse of refactor cost. |
| confidence | 0.12 | Quality of timing evidence (e.g., serial, repeated, above noise floor). |
| reversibility | 0.08 | How cleanly the change is undone if green-verify fails. |

## Skills

| Skill | Phase | Writes |
|---------|-------|--------|
| `/pytest-optimizer:00-scan` | Profile, detect, hypothesize | `baseline.json`, `capabilities.json`, `collection.txt`, `hypotheses.json` |
| `/pytest-optimizer:01-benchmark` | Prove each hypothesis vs the noise band | `benchmarks.json`, `control.json`, `patches/` |
| `/pytest-optimizer:02-plan` | Rank into a commit plan (plan-mode gated) | `plan.json` |
| `/pytest-optimizer:03-execute` | Apply each patch as a commit on a new branch, verify, resume | `execution-log.json`, the result branch |

Use `pytest-optimizer` as an orchestrator for conversational phrases like
"speed up my tests". The four phase skills are invoked by name only, so the
orchestrator reads each phase's `SKILL.md` and follows it.

## Memory

Durable state lives in `.pytest-optimizer/` at the repo root, or in a per-user
cache directory when the tree is read-only. Every phase looks it up in the same
order: `--memory-dir`, the in-tree directory, the cache directory. See
`references/memory-schema.md`.

## Prerequisites

- A git repository with a pytest suite.
- `python3` (3.9 or newer) on `PATH` for `scripts/measure.py` and `scripts/isolate.py`, which do the timing arithmetic and the Git isolation.
- A test command the skills can read from `AGENTS.md`, `CLAUDE.md`, `justfile`, `tox.ini`, or `pyproject.toml`.
- Optional auto-detected plugins: `pytest-xdist`, `pytest-randomly`,
  `pytest-deadfixtures`, `pytest-timeout`. The skills ask before installing any of them into your environment.

## Component reference

- `skills/00-scan`, `01-benchmark`, `02-plan`, `03-execute`: the four phase skills.
- `skills/pytest-optimizer/SKILL.md`: orchestrator with planning and
  degradation.
- `references/`: recipes, schemas, rubric, and capabilities.
- `scripts/measure.py`: median, MAD, noise band, test-count and node-id gates, rubric arithmetic, memory lookup, resume check.
- `scripts/isolate.py`: input digest, owned scratch worktrees, hash-bound patches, commit gate.
- `templates/`: opt-in scaffolds (timing plugin, cache snippet) and the commit message template.

## Scope

The pipeline is runner-agnostic, but the heuristics are pytest-specific
(degrading gracefully across the pytest versions in `references/version-matrix.md`).
