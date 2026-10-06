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
readiness gate passes.

Read `../../references/merge-readiness.md` before touching the PR.

User arguments: $ARGUMENTS

## Procedure

### 1. Identify the PR

Precedence: an explicit argument (number or URL) > the PR this
conversation has been working on > the current branch's PR. If the
candidates disagree, ask via `AskUserQuestion` before proceeding.

Gather the PR's state. A failure here means no PR exists for the branch or
`gh` is unavailable or unauthenticated: report it and stop.

```console
gh pr view <n> --json number,title,url,state,isDraft,baseRefName,mergeable,mergeStateStatus,reviewDecision
```

Trunk is the PR's `baseRefName`. With no argument and no conversation PR,
run `git branch --show-current` and `gh pr view` without `<n>` to find the
current branch's PR.

### 2. Run the readiness gate

Apply the readiness gate from the reference. If the PR is `BEHIND` or
`DIRTY`, confirm with the user, then follow the reference's rebase procedure.

### 3. Compose the merge commit message

Follow the reference's merge-commit-message section, which also says when to
skip it. Write the message per `../../references/prose-rules.md`.

### 4. Merge

Pass the user's `gh pr merge` flags through verbatim. The strategy flag is
`--merge` unless the user passed `--squash` or `--rebase`:

```console
gh pr merge <n> <strategy flag> -t "<subject>" -b "<body>"
```

Use `--admin` only within the reference's policy.

### 5. Sync trunk and stand by

Sync trunk and confirm the merge, per the reference's "After each merge".
Then stop.

## Output

Open with a one-line hero (`✓ Merged #N: <title>` or
`⚠ Blocked: <reason>`), then exactly these sections:

1. `## Merge readiness` — the gate results, including anything that
   required a rebase or a wait on CI.
2. `## Merge` — strategy used, flags passed through, and the merge
   commit subject (or why no merge happened).
3. `## Trunk` — the post-merge trunk state after checkout and pull.

Write the sections per `../../references/prose-rules.md`.

End with an `AskUserQuestion` panel offering next steps (for example:
cut a release from the merged trunk, merge another PR, delete the
local branch, stop here) — skip the panel only in plan mode.

Offer the release only when the merged trunk is in a releasable state and
the repo carries the version files a release touches. Name the project's
release skill or command if one exists; tagging and pushing stay the user's
explicit act.
