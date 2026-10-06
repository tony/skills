---
name: this
description: Merge one PR via gh with a merge commit matching the repo's git history — readiness-gated, CI-watched, trunk synced after
allowed-tools: ["Bash", "Read", "Grep", "Edit", "AskUserQuestion"]
argument-hint: "[PR number or URL] [--squash | --rebase | any other gh pr merge flag]"
user-invocable: true
disable-model-invocation: true
---

# Merge This PR

Merge a single pull request (the one this conversation is about, or the one
the current branch belongs to) via `gh pr merge`. Nothing merges until the
readiness gate passes. Report only what a command in this run verified.

Read `../../references/merge-readiness.md` before touching the PR.

User arguments: $ARGUMENTS

## Procedure

### 1. Identify the PR

Precedence: an explicit argument (number or URL) > the PR this
conversation has been working on > the current branch's PR. If the
candidates disagree, ask via `AskUserQuestion` before proceeding.

With no argument and no conversation PR, run `git branch --show-current`
and `gh pr view --json number` to find the current branch's PR.

Gather the PR's state. A failure here means no PR exists for the branch or
`gh` is unavailable or unauthenticated: report it and stop.

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
per `../../references/prose-rules.md`.

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
Then stop.

## Output

Open with a one-line hero (`✓ Merged #N: <title>` or
`⚠ Blocked: <reason>`), then exactly these sections. A run that stops before
the merge gives the hero, `## Merge readiness`, and one sentence on what the
user must do; nothing else.

1. `## Merge readiness` — the gate results, including anything that
   required a rebase or a wait on CI.
2. `## Merge` — strategy used, flags passed through, and the merge
   commit subject (or why no merge happened).
3. `## Trunk` — the post-merge trunk state after checkout and pull, or
   that the sync was skipped.

Write the sections per `../../references/prose-rules.md`.

End with an `AskUserQuestion` panel offering next steps (for example:
cut a release from the merged trunk, merge another PR, delete the
local branch, stop here) — skip the panel in plan mode. Without a question
tool, end after the sections: no `## Next steps` section.

Offer the release only when the merged trunk is in a releasable state and
the repo carries the version files a release touches. Name the project's
release skill or command if one exists; tagging and pushing stay the user's
explicit act.
