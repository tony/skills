# spike

Run no-commit spikes, strategy bakeoffs, or multi-round convergence loops in git
worktrees. Tests ideas against quality gates and returns a commit-by-commit
implementation plan.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install spike@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add spike@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/spike:probe [<goal>]` | `spike:probe [<goal>]` | Probe the goal with zero commits, stash with a recovery ref, propose a commit-by-commit landing plan |
| `/spike:bakeoff [<goal>]` | `spike:bakeoff [<goal>]` | Build 2–4 competing strategies in isolated worktrees, judge adversarially, stash contenders, propose landing plan for winner |
| `/spike:loop [<goal>]` | `spike:loop [<goal>]` | Run probes and bakeoffs in rounds until the design stops fighting back, accumulating a ledger of stumbling blocks and locked decisions |

The goal can be typed or inferred from conversation context (review
findings, failing tests) — the plan-mode brief confirms it.

`/spike:probe` flags: `--branch=<name>` (spike on scratch branch),
`--keep-tree` (skip stash, leave changes), `--replay` (implement
approved plan immediately via gated commits).

`/spike:bakeoff` flags: `--strategies="a; b; c"` (explicit contender
list), `--prongs=<2-4>` (cap contender count), `--keep-trees` (leave
worktrees), `--replay` (land winner immediately).

`/spike:loop` flags: `--rounds=<n>` (cap rounds, default 3),
`--replay` (land the converged result immediately).

One approach in mind → `probe`. Genuinely uncertain between two or
three named approaches → `bakeoff`. Shape of the answer still unknown,
so one pass of either will not settle it → `loop`. To vary the *model*
rather than the strategy, use the weave plugin.

## Workflow

1. **Situational awareness** — read AGENTS.md / CLAUDE.md to discover
   format / lint / test / build commands and post-push CI coverage.
2. **Spike brief** — confirm goal, "proven" criterion, and exit path.
3. **Probe** — shortest path to proven; cheapest verification signal
   only; shortcuts marked `SPIKE:`; stumbling blocks recorded.
4. **Exit gate** — fast local gates pass to ensure known state.
5. **Stash** — `git stash push -u` with descriptive message and
   recorded immutable SHA for recovery.
6. **Replay plan** — numbered commit sequence mapping stash hunks to
   commits, resolving decisions, and noting per-commit gates.

A bakeoff runs steps 3–5 once per contender in isolated worktrees,
adds an adversarial judging pass (correctness, blast radius, idiom
fit, gate status), then proposes a replay plan for the winner. Every
contender is stashed for recovery before its worktree is removed.

A loop repeats that cycle in rounds — probe, bake off the approaches
the probe's stumbling blocks put in doubt, re-probe the winner with
its grafts applied — and stops when a round surfaces nothing new, the
round cap is reached, or the same blocks keep recurring. Each round
appends to a ledger under the repository's git common directory,
where `git stash -u` and `git clean` cannot reach it and every
worktree resolves the same path. The ledger, not the code, is what a
loop is for: it feeds a clean rewrite or the closing landing plan.

The spike never commits locally or in worktrees. Commits only happen
via `--replay` after plan approval, one item at a time behind green gates.

## Verification discovery

Commands read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and CI definitions to learn push coverage
(see `references/verification-gates.md`). Does **not** hardcode
runners or linters, and deliberately limits verification to defer
CI-covered work to `gh pr checks --watch`.

## Prerequisites

- **git** — stash-based workflow; `/spike:bakeoff` and `/spike:loop`
  use `git worktree`. `/spike:loop` also needs git 2.31 or newer,
  which is where `git rev-parse --path-format` arrived; it resolves
  the ledger path with it.
- **gh** (optional) — enables watching CI checks after a push
