---
name: merge-pr-multiple
description: >-
  Merge a set of PRs one at a time: detect stack vs independent set, rebase
  and resolve conflicts, watch CI, merge each via gh
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Edit", "AskUserQuestion"]
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
`ask-user-choice` and let the user pick; without a question tool, halt and
list them. Show the final roster.

Read each roster PR's `mergeStateStatus` (`gh pr view <n> --json mergeStateStatus`).
When any is `BEHIND` or `DIRTY`, confirm via `ask-user-choice` before the
first merge, naming each such PR and its branch as a force-push
(`--force-with-lease --force-if-includes`). The approval also covers a
roster PR that falls behind after an earlier merge. Without a question tool,
or if the user declines, halt before any rebase or push. When every PR is
`CLEAN`, the approval is still asked at the first PR that needs a rebase.

List the open PRs to check the roster against. A failure means `gh` is
unavailable or unauthenticated: report it and stop. `--limit` lifts the
default cap of 30; a roster PR missing from the list is checked with
`gh pr view <n>` before it is called not open.

```console
$ gh pr list --limit 200 --json number,title,headRefName,baseRefName,isDraft
```

### 2. Detect the topology

Check the repo scope as the reference describes. Then have the helper read
each PR and order the set, passing `--repo` when the user did:

```console
$ python3 /absolute/path/to/scripts/merge_pr.py order <PR numbers in the user's order>
```

It prints the topology (`stack` when any PR's base branch is another PR's
head branch, else `independent`), the merge order (bottom-up for a stack,
otherwise the order given), the trunk, each PR's parent, and each
`headRefOid`; keep the `headRefOid` values for the stacked rebase. A `null`
trunk means the PRs target different branches: ask which is trunk, or halt
and list them without a question tool.

Resolve the absolute script path as the reference describes: `../../scripts/`
from this skill's directory.

For a stack, plan the retarget: after each parent merges, read the child's
`baseRefName` (`gh pr view <child> --json baseRefName`); when it is not
trunk, run `gh pr edit <child> --base <trunk>`, then re-read the child's
state, before its readiness gate.

### 3. Land each PR

One PR at a time; never merge two PRs between trunk syncs. For each PR in
order:

1. **Retarget** a stacked child whose parent just merged, as planned above.
2. **Readiness gate**: apply the gate from the reference, on the
   retargeted state. A halt reports what landed and what remains.
3. **Bring up to date**: when the PR is `BEHIND` or `DIRTY` (or `UNKNOWN`
   after the gate's retries) and the force-push is approved, follow the
   reference's rebase procedure; unapproved, ask as in step 1 or halt; with
   scope `remote` that halts the run. Leave a `CLEAN` PR alone: no rebase,
   no force-push. For a stacked child, use its `--onto` form with the
   parent's roster-time `headRefOid`, because a squash merge leaves the
   parent's old head out of trunk. Ask on any conflict that forces a choice
   between behaviors.
4. **Wait on CI**: `gh pr checks <n> --watch` only when the PR was rebased or
   the gate saw pending checks. A PR with no checks has no CI to wait on.
5. **Merge**: check the repo allows the strategy, compose the message per
   the reference and `references/prose-rules.md` (no `Co-Authored-By`,
   no "Generated with" or other tool trailer, no emoji), then merge with
   the reference's `merge_pr.py merge` command, never a message inside a
   shell string, with `--match-head-commit <sha>` and the strategy flag. Pass the
   user's other flags through verbatim, except `--delete-branch` on a stack
   parent: the reference drops it, and the report says so.
6. **Sync**: per the reference's "After each merge", including its check
   that trunk contains the merge commit and the subject read-back. A queued
   (`--auto`) merge halts the run here.

### 4. Halt conditions

Stop and report, never push past, when a rebase produces an
unexpected content diff, CI fails on a rebased head, a PR turned
closed or draft mid-run, or a conflict needs a product decision.
Everything already merged stays merged; the report says exactly
where the run stopped and why.

After the last PR of a stack merges, carry out the user's `--delete-branch`
for every branch still on the remote, per the reference's stack-parents section.

## Output

Open with a one-line hero (`✓ Merged N of M PRs`, or
`⚠ Merged N of M PRs; <trunk fact>` when a contains-the-merge-commit check
failed or a subject was not verified, or
`⚠ Halted at #N: <reason>`; an `--auto` merge halts with
`⚠ Halted at #N: queued with --auto, merges once checks pass`), then
exactly these sections. Report only what
a command in this run verified, and name the merge order only once the
topology was read. A run halted before any merge (`gh` unavailable, roster
invalid) gives the hero and one sentence on what the user must do; no
headings, and never a sentence saying what was not done ("nothing was
merged"). The hero states the cause only: not "so neither PR was merged".

1. `## Roster`: the PRs, detected topology (stack or independent),
   and merge order.
2. `## Merges`: one bullet per PR: the gate result, rebase and conflicts if
   any (a clean rebase is "rebased onto <base>; previous head <short sha>", nothing more), CI outcome, merge commit short SHA with its subject as read back from
   the commit. Note a dropped `--delete-branch` on a stack parent, and the
   parent branches deleted after the last merge. Diagnostics about the
   environment belong in no bullet. Name a flag only when the run
   dropped or added one; never the user's own flags.
3. `## Trunk`: the post-run trunk state and the result of the
   contains-the-merge-commit check. Report a mismatch as a fact with the
   short SHAs; give no cause.

State a failure as the fact the user needs; never quote the tool's error
text or explain how a check works. Follow the reference's "Report wording".
Write the sections per `references/prose-rules.md`, impersonally:
no first person.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ Halted at #32: CI failed on the rebased head.

## Roster

- Stack of 3 PRs, merged bottom-up: #31, #32, #33.

## Merges

- #31: gate passed, CI green, merged as 4f2a9c1 "sync(fix[client]) Retry transient network errors (#31)".
- #32: rebased onto main (previous head 9ad03e1); the type-check job failed. Not merged.
- #33: not attempted.

## Trunk

- main is at the #31 merge commit.
```

A run halted before any merge:

```text
⚠ Halted: gh is not authenticated.

Run `gh auth login`, then re-run `merge-pr-multiple #31 #32 --squash`.
```

End with an `ask-user-choice` panel offering next steps (for
example: continue with a halted PR after a fix, merge another set,
stop here); skip the panel in plan mode. Without a question tool, end
after the sections and say nothing about the missing panel; no
`## Next steps` section.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
