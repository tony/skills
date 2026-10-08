---
name: merge-pr-this
description: >-
  Merge one PR via gh with a merge commit matching the repo's git history;
  readiness-gated, CI-watched, trunk synced after
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
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
gate reuses this read. When the user passed `--repo`, add it to this command
and every other `gh` call, and check the repo scope as the reference
describes.

```console
$ gh pr view <n> --json number,title,url,state,isDraft,baseRefName,mergeable,mergeStateStatus,reviewDecision
```

Trunk is the PR's `baseRefName`.

### 2. Run the readiness gate

Apply the readiness gate from the reference. If the PR is `BEHIND` or
`DIRTY` and the repo scope is `local`, confirm with the user, then follow the
reference's rebase procedure. Without a question tool, halt instead of
rebasing. With scope `remote`, halt: the rebase cannot run here.

### 3. Compose the merge commit message

Check the repo allows the strategy, per the reference's strategy section.
Then follow its merge-commit-message section, which also says when to skip
it (`--rebase`, or a message flag from the user). Write the message per
`references/prose-rules.md`. The message carries no `Co-Authored-By`,
no "Generated with" or other tool trailer, and no emoji.

### 4. Merge

Pass the user's `gh pr merge` flags through verbatim, with the strategy flag
and `--match-head-commit <sha>`. Pass the composed message through the
reference's `merge_pr.py merge` command, never inside a shell string. Use
`--admin` only within the reference's policy.

### 5. Sync trunk and stand by

Sync trunk and confirm the merge, per the reference's "After each merge",
including its check that trunk contains the merge commit. Then stop.
When the merge is only queued (`--auto`, or `state` still `OPEN` after the
merge), open with the queued hero and skip the sync.

## Output

Open with a one-line hero (`✓ Merged #N: <title>`,
`✓ Queued #N: <title>` for an `--auto` merge, or `⚠ Blocked: <reason>`),
then exactly these sections. A run that stops before
the merge (including `gh` unavailable: `⚠ Blocked: gh is not authenticated`)
gives the hero and one sentence on what the user must do; no
headings, and never a sentence saying what was not done ("nothing was
merged", "I did not use --admin"). The hero states the cause only.

1. `## Merge readiness`: the gate results, including anything that
   required a rebase or a wait on CI.
2. `## Merge`: the strategy, the merge commit short SHA with its subject
   as read back from the commit, and the PR URL. A queued merge gives the
   strategy and the PR URL (its reply keeps all three sections; see the
   queued example). Name a flag only when the run dropped or added
   one the user did not pass; never the head pin or the user's own flags.
   Say nothing about the title's characters or how the message was passed.
3. `## Trunk`: the post-merge trunk state and the result of the
   contains-the-merge-commit check, or that the sync was skipped and why.
   Report a mismatch as a fact with the short SHAs; give no cause and do
   not narrate how the pull was run.

State a failure as the fact the user needs; never quote the tool's error
text or explain how a check works. Follow the reference's "Report wording".
Write the sections per `references/prose-rules.md`.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

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

A queued run (`--auto`) uses the same three sections, with readiness as
in a merged run:

```text
✓ Queued #31: Retry transient sync failures

## Merge readiness

- Open, not a draft. CI green on the head.

## Merge

- Strategy --squash. GitHub merges it once the required checks pass.
- https://github.com/acme/widgets/pull/31

## Trunk

- Sync skipped: the merge has not happened yet.
```

A stopped run:

```text
⚠ Blocked: #42 needs an approving review before branch protection allows the merge.

Get the review, or tell me to merge with --admin.
```

End with an `ask-user-choice` panel offering next steps (for example:
cut a release from the merged trunk, merge another PR, delete the
local branch, stop here); skip the panel in plan mode. Without a question
tool, end after the sections and say nothing about the missing panel; no
`## Next steps` section.

Offer the release only when the merged trunk is in a releasable state and
the repo carries the version files a release touches. Name the project's
release skill or command if one exists; tagging and pushing stay the user's
explicit act.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
