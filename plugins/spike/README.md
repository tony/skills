# spike

Run no-commit spikes, strategy bakeoffs, or multi-round convergence in git
worktrees. Tests ideas against quality gates and returns a commit-by-commit
implementation plan.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install spike@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add spike@skills
```

## Skills

Probe one path with zero commits, stash the result with a recovery ref,
and get a commit-by-commit landing plan:

```text
/spike:probe [<goal>]
```

Build two to four competing strategies in isolated worktrees, judge them
adversarially, and get a landing plan for the winner:

```text
/spike:bakeoff [<goal>]
```

Run probes and bakeoffs in rounds until the design stops fighting back,
keeping a ledger of stumbling blocks and locked decisions:

```text
/spike:ratchet [<goal>]
```

Codex omits the leading slash (`spike:probe`). Each skill's flags are in
its `SKILL.md`.

The goal can be typed or inferred from conversation context (review
findings, failing tests); the plan-mode brief confirms it.

One approach in mind: `probe`. Genuinely uncertain between two or
three named approaches: `bakeoff`. Shape of the answer still unknown, so
one pass of either will not settle it: `ratchet`. To vary the *model*
rather than the strategy, use the weave plugin.

A spike never commits. Commits happen only through `--replay`, after plan
approval, one item at a time behind green gates. A repository whose root
contains your home directory is refused, and uncommitted work is stashed
or kept in the tree, never discarded.

## Verification discovery

Commands read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and CI definitions to learn push coverage
(see `references/verification-gates.md`). Does **not** hardcode
runners or linters, and deliberately limits verification to defer
CI-covered work to `gh pr checks --watch`.

## Prerequisites

- **git**: stash-based workflow; `/spike:bakeoff` and `/spike:ratchet`
  use `git worktree`. `/spike:ratchet` also needs git 2.31 or newer,
  which is where `git rev-parse --path-format` arrived; it resolves
  the ledger path with it.
- **gh** (optional): enables watching CI checks after a push
