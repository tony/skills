---
name: merge-pr-this
description: >-
  Merge one PR via gh with a merge commit matching the repo's git history —
  readiness-gated, CI-watched, trunk synced after
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[PR number or URL] [--squash | --rebase | any other gh pr merge flag]"
  source: "plugins/merge-pr/skills/this/SKILL.md"
---

# Merge This PR

Merge a single pull request (the one this conversation is about, or the one
the current branch belongs to) via `gh pr merge`. Nothing merges until the
readiness gate passes. Report only what a command in this run verified.

Read `references/merge-readiness.md` before touching the PR.

User arguments: $ARGUMENTS

## Procedure

### 1. Identify the PR

Precedence: an explicit argument (number or URL) > the PR this
conversation has been working on > the current branch's PR. If the
candidates disagree, ask via `ask-user-choice` before proceeding; without a
question tool, halt and list them.

With no argument and no conversation PR, run `git branch --show-current`
and `gh pr view --json number` to find the current branch's PR.

Gather the PR's state. A failure here means no PR exists for the branch or
`gh` is unavailable or unauthenticated: report it and stop. The readiness
gate reuses this read.

```console
$ gh pr view <n> --json number,title,url,state,isDraft,baseRefName,mergeable,mergeStateStatus,reviewDecision
```

Trunk is the PR's `baseRefName`.

### 2. Run the readiness gate

Apply the readiness gate from the reference. If the PR is `BEHIND` or
`DIRTY`, confirm with the user, then follow the reference's rebase procedure.
Without a question tool, halt instead of rebasing.

### 3. Compose the merge commit message

Follow the reference's merge-commit-message section, which also says when
to skip it (`--rebase`, or a message flag from the user). Write the message
per `references/prose-rules.md`.

### 4. Merge

Pass the user's `gh pr merge` flags through verbatim. The strategy flag is
`--merge` unless the user passed `--squash` or `--rebase`. Add
`--match-head-commit <sha>` per the reference. Add `-t`/`-b` only under the
reference's condition:

```console
$ gh pr merge <n> <strategy flag> --match-head-commit <sha> -t "<subject>" -b "<body>"
```

Use `--admin` only within the reference's policy.

### 5. Sync trunk and stand by

Sync trunk and confirm the merge, per the reference's "After each merge".
Then stop. With `--auto` the merge is only queued: say so and skip the sync.

## Output

Open with a one-line hero (`✓ Merged #N: <title>` or
`⚠ Blocked: <reason>`), then exactly these sections. A run that stops before
the merge gives the hero and one sentence on what the user must do; no
headings, and no narration of what was not done.

1. `## Merge readiness` — the gate results, including anything that
   required a rebase or a wait on CI.
2. `## Merge` — strategy used, flags passed through, the merge commit
   subject and short SHA, and the PR URL.
3. `## Trunk` — the post-merge trunk state after checkout and pull, or
   that the sync was skipped.

Write the sections per `references/prose-rules.md`.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
✓ Merged #31: Retry transient sync failures

## Merge readiness

- Open, not a draft. CI green on the head after a wait on the lint job.
- Behind main by one commit; rebased and force-pushed with the user's approval.

## Merge

- Strategy --merge, no extra flags. Merge commit 4f2a9c1: "sync(fix[client]) Retry transient network errors (#31)".
- https://github.com/acme/widgets/pull/31

## Trunk

- main is at the merge commit; local main fast-forwarded.
```

A stopped run:

```text
⚠ Blocked: #42 needs an approving review before branch protection allows the merge.

Get the review, or tell me to use --admin; I did not use it.
```

End with an `ask-user-choice` panel offering next steps (for example:
cut a release from the merged trunk, merge another PR, delete the
local branch, stop here) — skip the panel in plan mode. Without a question
tool, end after the sections: no `## Next steps` section.

Offer the release only when the merged trunk is in a releasable state and
the repo carries the version files a release touches. Name the project's
release skill or command if one exists; tagging and pushing stay the user's
explicit act.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
