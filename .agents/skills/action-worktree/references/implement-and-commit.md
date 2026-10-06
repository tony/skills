# Implement and commit

The per-unit procedure for a ticket branch, run inside its worktree.
this skill follows it in its own turn; the `action-worktrees` skill hands
it to each executor.

Work inside the assigned worktree only. Never run `git fetch`,
`git stash`, or `git worktree` subcommands, and never touch paths
outside the worktree. Tickets are read-only: no assign, comment,
transition, label, or `gh issue develop`; every tracker operation is a
read.

## Implement

1. Work the acceptance criteria in the project's idiom.
2. Verify with the cheapest signal that moves you forward: the one test
   file or smoke command exercising the change. Full passes wait for
   the gates.
3. Stay in ticket scope. Adjacent problems go in the report's
   "observed, not addressed" list, not in the diff.
4. Multi-ticket: keep each ticket's work separable, so every commit is
   attributable to its ticket ID(s).

## Gates and commit

1. Run the fast local buckets exactly as discovered (`format`, `lint`,
   `typecheck`, scoped `test`; `build` only when plausibly affected)
   as resolved in the plan. Gates run as discovered,
   including mutating ones such as `--fix` linters: fold autofixes into
   the commit under test and re-run the scoped test once when a gate
   changed files.
2. Green: commit in the project's format. Each commit body names the
   ticket ID(s) it advances, in the project's form. Write the message per
   `prose-rules.md`. Closing keywords
   belong in the PR body, never in commit subjects. Multi-ticket
   branches land one commit per separable unit of work where practical.
3. Red: fix and re-run. A gate that cannot be brought green stops the
   unit before any push or PR. Report the failure verbatim under
   `## Verification` and leave the worktree in place for inspection.
   One unit's failure never blocks other units.
