---
name: multiple
description: Merge a set of PRs one at a time — detect stack vs independent set, rebase and resolve conflicts between merges, watch CI, merge each via gh
allowed-tools: ["Bash", "Read", "Grep", "Edit", "AskUserQuestion"]
argument-hint: "[PR numbers/URLs, e.g. '#31 #32'] [--squash | --rebase | any other gh pr merge flag]"
user-invocable: true
disable-model-invocation: true
---

# Merge Multiple PRs

Land a set of pull requests one at a time: merge one, refresh trunk,
bring the next PR up to date (rebase, resolve conflicts, force-push,
wait on CI), then merge it, repeating until the set is landed or a
gate halts the run.

Read `../../references/merge-readiness.md` before touching any PR.

User arguments: $ARGUMENTS

## Procedure

### 1. Assemble the roster

Take the PR set from the arguments, or from the PRs this
conversation has been working on. If the set is ambiguous (the
conversation touched more PRs than the user likely means, or an
argument doesn't match an open PR), present the candidates via
`AskUserQuestion` and let the user pick; without a question tool, halt and
list them. Show the final roster
before merging anything.

List the open PRs to check the roster against. A failure means `gh` is
unavailable or unauthenticated: report it and stop. `--limit` lifts the
default cap of 30; a roster PR missing from the list is checked with
`gh pr view <n>` before it is called not open.

```console
$ gh pr list --limit 200 --json number,title,headRefName,baseRefName,isDraft
```

### 2. Detect the topology

Fetch `baseRefName`, `headRefName`, and `headRefOid` for each PR
(`gh pr view <n> --json baseRefName,headRefName,headRefOid`); keep each
`headRefOid` for the stacked rebase. If any PR's base
branch is another PR's head branch, the set is a **stack**: order
bottom-up, each PR merging only after its parent. Otherwise the set
is **independent**: honor the order the user gave, falling back to
ascending PR number.

Trunk is the `baseRefName` of the bottom PR of a stack, or of the
independent PRs.

For a stack, plan the retarget: after each parent merges, read the child's
`baseRefName` (`gh pr view <child> --json baseRefName`); when it is not
trunk, run `gh pr edit <child> --base <trunk>` before rebasing the child.

### 3. Land each PR

One PR at a time; never merge two PRs between trunk syncs. For each PR in
order:

1. **Readiness gate** — apply the gate from the reference. A halt
   reports what landed and what remains.
2. **Bring up to date** — when the PR is `BEHIND` or `DIRTY`, or an
   earlier merge in this run moved trunk, follow the reference's rebase
   procedure. For a stacked child, run
   `git rebase --onto <trunk> <parent's recorded headRefOid> <branch>` so
   the parent's merged commits drop out; a squash merge deletes the
   parent's old head, so use the roster-time SHA. Ask on any conflict that forces a choice
   between behaviors.
3. **Wait on CI** — `gh pr checks <n> --watch` on the rebased head.
4. **Merge** — compose the message per the reference and
   `../../references/prose-rules.md`, then merge with
   `gh pr merge <n> <strategy flag> --match-head-commit <sha>`, plus
   `-t`/`-b` only under the reference's condition, passing the user's
   flags through verbatim. The strategy flag is `--merge` unless the user
   passed `--squash` or `--rebase`. `--admin` only within the reference's
   policy.
5. **Sync** — per the reference's "After each merge". A queued
   (`--auto`) merge halts the run here.

### 4. Halt conditions

Stop and report, never push past, when a rebase produces an
unexpected content diff, CI fails on a rebased head, a PR turned
closed or draft mid-run, or a conflict needs a product decision.
Everything already merged stays merged; the report says exactly
where the run stopped and why.

## Output

Open with a one-line hero (`✓ Merged N of M PRs` or
`⚠ Halted at #N: <reason>`), then exactly these sections. Report only what
a command in this run verified, and name the merge order only once the
topology was read. A run halted before any merge (`gh` unavailable, roster
invalid) gives the hero and one sentence on what the user must do; no
headings, and no narration of what was not done.

1. `## Roster` — the PRs, detected topology (stack or independent),
   and merge order.
2. `## Merges` — per PR: gate result, rebase/conflicts if any, CI
   outcome, merge commit subject and short SHA.
3. `## Trunk` — the post-run trunk state, from the sync's checkout and pull.

Write the sections per `../../references/prose-rules.md`.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
⚠ Halted at #32: CI failed on the rebased head.

## Roster

- Stack of 3 PRs, merged bottom-up: #31, #32, #33.

## Merges

- #31: gate passed, CI green, merged as 4f2a9c1 "sync(fix[client]) Retry transient network errors (#31)".
- #32: rebased onto main; the type-check job failed. Not merged.
- #33: not attempted.

## Trunk

- main is at the #31 merge commit.
```

End with an `AskUserQuestion` panel offering next steps (for
example: continue with a halted PR after a fix, merge another set,
stop here) — skip the panel in plan mode. Without a question tool, end
after the sections: no `## Next steps` section.
