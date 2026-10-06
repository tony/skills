---
name: merge-pr-multiple
description: >-
  Merge a set of PRs one at a time — detect stack vs independent set, rebase
  and resolve conflicts between merges, watch CI, merge each via gh
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[PR numbers/URLs, e.g. '#31 #32'] [--squash | --rebase | any other gh pr merge flag]"
  source: "plugins/merge-pr/skills/multiple/SKILL.md"
---

# Merge Multiple PRs

Land a set of pull requests one at a time: merge one, refresh trunk,
bring the next PR up to date (rebase, resolve conflicts, force-push,
wait on CI), then merge it, repeating until the set is landed or a
gate halts the run.

Read `references/merge-readiness.md` before touching any PR.

User arguments: $ARGUMENTS

## Procedure

### 1. Assemble the roster

Take the PR set from the arguments, or from the PRs this
conversation has been working on. If the set is ambiguous (the
conversation touched more PRs than the user likely means, or an
argument doesn't match an open PR), present the candidates via
`ask-user-choice` and let the user pick. Show the final roster
before merging anything.

List the open PRs to check the roster against. A failure means `gh` is
unavailable or unauthenticated: report it and stop.

```console
gh pr list --json number,title,headRefName,baseRefName,isDraft
```

### 2. Detect the topology

Fetch `baseRefName` and `headRefName` for each PR. If any PR's base
branch is another PR's head branch, the set is a **stack**: order
bottom-up, each PR merging only after its parent. Otherwise the set
is **independent**: honor the order the user gave, falling back to
ascending PR number.

Trunk is the `baseRefName` of the bottom PR of a stack, or of the
independent PRs.

For a stack, plan the retarget: merging a parent with
`--delete-branch` lets GitHub retarget the child to trunk
automatically; when the branch is kept, retarget explicitly with
`gh pr edit <child> --base <trunk>` before rebasing the child.

### 3. Land each PR

One PR at a time; never merge two PRs between trunk syncs. For each PR in
order:

1. **Readiness gate** — apply the gate from the reference. A halt
   reports what landed and what remains.
2. **Bring up to date** — when the PR is `BEHIND` or `DIRTY`, or an
   earlier merge in this run moved trunk, follow the reference's rebase
   procedure. For a stacked child, `git rebase --onto` the new trunk so the
   parent's merged commits drop out. Ask on any conflict that forces a choice
   between behaviors.
3. **Wait on CI** — `gh pr checks <n> --watch` on the rebased head.
4. **Merge** — compose the message per the reference and
   `references/prose-rules.md`, then merge with
   `gh pr merge <n> <strategy flag> -t ... -b ...`, passing the user's
   flags through verbatim. The strategy flag is `--merge` unless the user
   passed `--squash` or `--rebase`. `--admin` only within the reference's
   policy.
5. **Sync** — per the reference's "After each merge".

### 4. Halt conditions

Stop and report, never push past, when a rebase produces an
unexpected content diff, CI fails on a rebased head, a PR turned
closed or draft mid-run, or a conflict needs a product decision.
Everything already merged stays merged; the report says exactly
where the run stopped and why.

## Output

Open with a one-line hero (`✓ Merged N of M PRs` or
`⚠ Halted at #N: <reason>`), then exactly these sections:

1. `## Roster` — the PRs, detected topology (stack or independent),
   and merge order.
2. `## Merges` — per PR: gate result, rebase/conflicts if any, CI
   outcome, merge commit subject.
3. `## Trunk` — the post-run trunk state.

Write the sections per `references/prose-rules.md`.

End with an `ask-user-choice` panel offering next steps (for
example: continue with a halted PR after a fix, merge another set,
stop here) — skip the panel only in plan mode.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
