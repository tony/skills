# spike

Run no-commit spikes, strategy bakeoffs, or multi-round convergence in git
worktrees. Tests ideas against quality gates and returns a commit-by-commit
implementation plan.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install spike --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

A spike never commits; `--replay` is the only path to a commit.

## Verification discovery

Commands read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and CI definitions to learn push coverage
(see `references/verification-gates.md`). No runner or linter is
hardcoded, and CI-covered work is deferred to `gh pr checks --watch`.

## Prerequisites

- git 2.31 or newer: stash-based workflow, `git switch`, and
  `git rev-parse --path-format` for the ratchet's ledger path.
  `/spike:bakeoff` and `/spike:ratchet` use `git worktree`.
- bash: `scripts/spike.sh` holds the git plumbing.
- python3 (3.14 or newer): runs `scripts/test_spike.py`.
- gh (optional): enables watching CI checks after a push.
