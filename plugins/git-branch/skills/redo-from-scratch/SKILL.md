---
name: redo-from-scratch
description: "Use when a branch or proof of concept should be redone from scratch: throw away the approach, start implementation over, and treat tests as the spec."
user-invocable: true
argument-hint: "[PR number, branch, or what should change about the approach]"
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob", "AskUserQuestion"]
---

# Redo from scratch

Throw the implementation away and write it again, without losing what
the original learned.

Argument: $ARGUMENTS — a PR number, a branch, a statement of what
should change about the approach, or nothing.

Five references carry the parts that must not drift:

- `../../references/rebuild-contract.md` — the
  contract, the coverage ledger, reconciliation, and what counts as
  done.
- `../../references/branch-safety.md` — the gates, the
  backup, recovery, and the push.
- `../../references/commit-messages.md` — style
  discovery, intent recovery, and the privacy gate.
- `../../references/rebase-toolkit.md` — per-commit
  verification with no editor, and `<toolkit>`.
- `../../references/split-mechanics.md` — committing whole files and
  splitting one file across commits.

## Core principle

The old branch is the specification, not the source.

Work from what the branch had to *achieve*; read how it achieved it
only when the requirement is ambiguous. Retyping the old code
reproduces the shape the redo exists to replace.

## Boundary

`/git-branch:soft-reset-and-recommit` keeps the net change identical
and rebuilds only the history; use it when the code is right and the
commits are wrong. This skill replaces both, and the net change may
differ, so the contract replaces the tree comparison as the safety.

## Phase 1 — Establish the contract before anything else

Per `rebuild-contract.md`. Identify trunk's tests, the tests this
branch added or changed, and run them against the branch now. What
passes is the specification; what is already failing or skipped is a
finding to report, not a target.

**If the branch has no tests, stop here.** An untested branch has no
mechanical invariant, and a redo becomes a rewrite with review as
the only net. Offer to write characterization tests against the
existing implementation first, so a spec exists before anything is
discarded. Proceed without them only if the user says so, and say in
the final report that nothing mechanical was guarding the result.

## Phase 2 — Study the branch into a ledger

Build the coverage ledger from `rebuild-contract.md`: behavior
changes, tests, edge cases and workarounds, review requests, ticket
acceptance criteria, public surface, dependencies.

Mine intent per `commit-messages.md` Part 2, to reconstruct requirements: commits, trailers, the
pull request and its review threads, linked tickets, and optionally
the session that wrote the code, under the privacy rules there.

Give the workarounds disproportionate attention: a guard with no test
and no comment is the thing a clean rewrite most likely drops.

## Phase 3 — Gate and back up

Every refusal in `branch-safety.md`, then the backup branch for the
original tip, per `branch-safety.md`. Never delete or force-move the old
branch, and never rebuild on it.

## Orchestration Plan

Enter plan mode before writing any code. In Claude Code that is
`EnterPlanMode`; in other hosts `/plan` or Shift+Tab. If plan mode is
unavailable, present the same plan inline and wait for a go-ahead.

The plan states:

- The contract: which tests are the spec, and their current result.
- The ledger, summarized, with the entries judged highest-risk called
  out by name.
- What is being changed about the approach, and why the original shape
  is not being kept.
- Where the rebuild happens — the worktree path and new branch name.
- The gate commands discovered from the project's own conventions.
- Anything the branch does that the rebuild intends to drop, as an
  explicit list to be approved rather than discovered later.

When several approaches contend, offer a bakeoff rather than picking
silently.

Wait for approval. Exit plan mode before executing. Without an
interactive question tool, stop after presenting the plan; an
instruction to redo authorizes the redo, not a push.

## Phase 4 — Rebuild

Work in a worktree so the original branch stays runnable for
comparison:

```
git worktree add -b <branch>-redo /tmp/<branch>-redo <base-sha>
```

Rebuild against the ledger, in the project's idiom, with no commits
until the contract is met. Mark shortcuts in place as you take them.

When the plan called for a bakeoff and a bakeoff skill is available,
run the competing strategies in isolated worktrees and compare them.
Otherwise build the leading candidate, record the alternatives, and say
they were not tried.

## Phase 5 — Verify against the contract

Trunk's tests, then the branch's tests, unmodified.

A test the rebuild cannot pass without editing is a decision, not a
task. Stop and surface it: the choices are to fix the rebuild, or to
agree the test encoded something the new approach deliberately
changes. Never edit a spec test to make a rebuild green.

## Phase 6 — Commit the series

Commit the rebuild as an atomic series in the project's own format,
per `commit-messages.md` (write the messages per
`../../references/prose-rules.md`; no `Co-Authored-By`, "Generated
with" or other tool trailer, and no emoji), carving the working tree into commits with
`split-mechanics.md` ("Commit whole files", "Split one file across
several commits").

Then gate every commit of the new series in place, with `<toolkit>` as
defined in `rebase-toolkit.md`:

```
sh <toolkit> verify <base-sha> '<test command>'
```

## Phase 7 — Reconcile, then stop

Walk the ledger per `rebuild-contract.md`. Record each deliberate drop
in the commit message that drops it; a miss is a defect.

Then present the comparison as review material, never as a gate:

```
git diff <backup-branch> <branch>-redo
```

Each hunk where the old branch did something the new one does not is a
question for the user. This is where a lost workaround surfaces.

Write the report per `../../references/prose-rules.md`. Reply in this
shape, as plain text outside any code fence, with plain bullets and no
bold (never `- **Ledger:** ...`):

```text
Rebuilt feature/export-v2 as feature/export-v2-redo; the contract holds.

- Contract: 48 trunk and branch tests pass unmodified.
- Ledger: 14 of 15 entries covered; 1 dropped on purpose.
- Dropped: the CSV retry shim, recorded in commit 3f9a0c1.
- Backup: backup/feature/export-v2-20261005.
- Not pushed.
```

A run stopped at Phase 1 or a refusal is one result sentence naming
why, then what the user must do. It claims no work that was not done.

Pushing is a separate decision, with the flags from
`branch-safety.md`. The old branch stays until the user retires it.
