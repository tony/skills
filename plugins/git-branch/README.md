# git-branch

Rebuild branch history into atomic commits (byte-identical), or reimplement
from scratch using existing tests as the spec. Includes an interactive-rebase
toolkit.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install git-branch@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add git-branch@skills
```

Claude Code uses a leading slash (`/git-branch:…`). Codex omits it (`git-branch:…`).

## Components

### `/git-branch:soft-reset-and-recommit` (skill)

Converts messy `wip` commits into a readable, reviewable series. Pushing is
always a manual step.

1. **Gathers intent:** Reads commit messages, trailers, PR bodies, reviews,
   and linked tickets before altering boundaries.
2. **Resolves base & validates:** Stops on dirty trees, operations in
   progress, and merge commits; asks before rewriting a pushed branch and
   stops if someone else pushed. Identifies correct base for
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
  only what the tests and the coverage ledger cover.

### The interactive-rebase toolkit

`scripts/rebase-todo.sh` drives `git rebase -i` without an editor or TTY.

Run it from anywhere. In the examples, `<toolkit>` is the script's absolute
path: the plugin's install path plus `scripts/rebase-todo.sh`.

Report any git operation in progress:

```console
$ sh <toolkit> status
```

Print the todo list for a range:

```console
$ sh <toolkit> show <base>
```

Replay the range from an edited plan:

```console
$ sh <toolkit> apply <base> plan.txt
```

Run a command after every commit, in place:

```console
$ sh <toolkit> verify <base> 'make test'
```

Fold pending `fixup!` and `amend!` commits:

```console
$ sh <toolkit> squash <base>
```

## Relationship to other git plugins

- **Use `/git-branch:soft-reset-and-recommit`**: When the branch content is
  correct but history is messy.
- **Use `/slop:deslop`**: When commit messages need cleaning but boundaries are
  fine (uses autosquash without splitting commits).
- **Use `/rebase:rebase`**: When moving a branch onto the current trunk.
- **Use `/commit:commit`**: When creating a new commit rather than rebuilding
  existing ones.

## Prerequisites

- **git** — 2.30+ for `--force-if-includes`; 2.38+ for
  `RECUT_UPDATE_REFS` (`--update-refs`).
  Check with `git --version`.
- **gh** — (Optional) to read PRs, reviews, and linked issues. Degrades to
  git-only if missing.
