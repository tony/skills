# git-branch

Rebuild branch history into atomic commits (byte-identical), or reimplement
from scratch using existing tests as the spec. Includes an interactive-rebase
toolkit.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install git-branch --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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
always a manual step. It refuses unless the target branch is checked out.
Signatures are lost unless `RECUT_SIGN` is set.

1. **Gathers intent:** Reads commit messages, trailers, PR bodies, reviews,
   and linked tickets before altering boundaries.
2. **Resolves base & validates:** Stops on dirty trees, operations in
   progress, and merge commits; asks before rewriting a pushed branch
   (including one pushed without `-u`) and stops if someone else pushed.
   Uses the merge base with the parent for stacked branches.
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

- **`soft-reset-and-recommit`**: History is messy; the code is correct.
  Guarantees byte-identical changes.
- **`redo-from-scratch`**: Code approach needs changing. Guarantees
  only what the tests and the coverage ledger cover.

### The interactive-rebase toolkit

`scripts/rebase-todo.sh` drives `git rebase -i` without an editor or TTY.

Run it from anywhere. The subcommands (`status`, `show`, `apply`,
`verify`, `squash`) and their exit codes are in
[`references/rebase-toolkit.md`](references/rebase-toolkit.md). It needs a
POSIX shell (WSL or Git Bash on Windows).

### The gate script

`scripts/branch_gate.py` carries the deterministic steps the skills would
otherwise re-derive: `preflight` (every refusal, with a code and a reason),
`base`, `backup`, `remote-tip`, `staged`, `hunks`, `changed` and `carry`,
and `series`. The refusal codes, the backup name, and the push form are in
[`references/branch-safety.md`](references/branch-safety.md). It runs under
the stock `python3` (3.9 or later) and needs nothing installed.

## Relationship to other plugins

Other plugins in this marketplace may cover cleaning commit messages without moving
boundaries, rebasing a branch onto trunk, or writing a new commit. Use
`/git-branch:soft-reset-and-recommit` when the branch content is correct
but its history is messy.

## Prerequisites

- **git**: 2.38+ for `RECUT_UPDATE_REFS` (`--update-refs`). Check with
  `git --version`.
- **python3**: 3.14+ for `scripts/branch_gate.py`.
- **gh**: (Optional) to read PRs, reviews, and linked issues. Degrades to
  git-only if missing.
