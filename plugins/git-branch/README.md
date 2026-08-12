# git-branch

Rebuild branch history into atomic commits (byte-identical), or reimplement
from scratch using existing tests as the spec. Includes an interactive-rebase
toolkit.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install git-branch@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add git-branch@skills
```

The skills below use Claude Code's leading slash. Codex uses the same names
without it (`git-branch:…`).

## Components

### `/git-branch:soft-reset-and-recommit` (skill)

Converts messy `wip` commits into a readable, reviewable series. Pushing is
always a manual step.

1. **Gathers intent:** Reads commit messages, trailers, PR bodies, reviews,
   and linked tickets before altering boundaries.
2. **Resolves base & validates:** Stops on dirty trees, operations in
   progress, merge commits, or pushed branches. Identifies correct base for
   stacked branches.
3. **Discovers commit format:** Reads from `AGENTS.md`, `CONTRIBUTING.md`,
   commitlint configs, or mining history. Asks if mixed.
4. **Plans and waits:** Presents proposed commits and contents for approval
   before making destructive changes.
5. **Backs up and rebuilds:** Creates a backup, performs `git reset --soft`,
   and recreates atomic commits preserving authorship and trailers.
6. **Proves identical state:** Ensures `git diff --quiet` exits 0 against the
   backup and runs project checks on every commit.

### `/git-branch:redo-from-scratch` (skill)

Reimplements flawed branch code cleanly using tests as the specification.
Retains original branch as a reference.

1. **Establishes test contract:** Uses passing trunk tests and branch tests as
   the spec. Requires characterization tests if none exist.
2. **Studies branch coverage:** Logs behavior changes, edge cases,
   workarounds, and public surface to prevent regression.
3. **Rebuilds from ledger in worktree:** Rewrites based on gathered
   requirements, avoiding line-by-line copying.
4. **Verifies contract:** Any failing test requiring edits triggers user review.
5. **Reconciles:** Validates all ledger entries are addressed and reviews the
   old-vs-new diff.

### Which skill to use

- **`soft-reset-and-recommit`**: Code is correct, but history is messy.
  Guarantees byte-identical changes.
- **`redo-from-scratch`**: Code approach needs changing. Guarantees
  correctness via test contracts and coverage ledgers.

### The interactive-rebase toolkit

`references/rebase-todo.sh` drives `git rebase -i` without an editor or TTY.

Run it from anywhere (substitute `${CLAUDE_PLUGIN_ROOT}` with the plugin's
install path outside a session):

Report any git operation in progress:

```console
sh ${CLAUDE_PLUGIN_ROOT}/references/rebase-todo.sh status
```

Print the todo list for a range:

```console
sh ${CLAUDE_PLUGIN_ROOT}/references/rebase-todo.sh show <base>
```

Replay the range from an edited plan:

```console
sh ${CLAUDE_PLUGIN_ROOT}/references/rebase-todo.sh apply <base> plan.txt
```

Run a command after every commit, in place:

```console
sh ${CLAUDE_PLUGIN_ROOT}/references/rebase-todo.sh verify <base> 'make test'
```

Fold pending `fixup!` and `amend!` commits:

```console
sh ${CLAUDE_PLUGIN_ROOT}/references/rebase-todo.sh squash <base>
```

## Relationship to other git plugins

- **Use `/git-branch:soft-reset-and-recommit`**: When the branch content is
  correct but history is messy.
- **Use `/pr:deslop`**: When commit messages need cleaning but boundaries are
  fine (uses autosquash without splitting commits).
- **Use `/rebase`**: When moving a branch onto the current trunk.
- **Use `/commit`**: When creating a new commit rather than rebuilding
  existing ones.

## Prerequisites

- **git** — 2.43+ for verified `--keep-base`, `git restore`, and
  `--force-if-includes` behavior.
- **gh** — (Optional) to read PRs, reviews, and linked issues. Degrades to
  git-only if missing.
- **uvx** — (Optional) for the prior-conversation layer.
