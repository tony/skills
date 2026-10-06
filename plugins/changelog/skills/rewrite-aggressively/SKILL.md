---
name: rewrite-aggressively
description: Rebase out the branch's earlier changelog commits and regenerate its entries fresh; commits only with --commit
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "[--commit] [optional additional context about the changes]"
user-invocable: true
disable-model-invocation: true
---

# Rewrite Changelog Entries Aggressively

Remove the changelog commits this branch accumulated, then regenerate its
entries from the branch's current net change. With `--commit`, the regenerated
entries land as one fresh commit at the tip; otherwise they stay as an
uncommitted edit. `/changelog:refresh` stacks a correcting commit on top; this
skill rewrites the branch so its changelog history collapses to one commit.

Scope: only the branch's own changelog content is rewritten. Base-branch
changelog content and the branch's code history are never modified; only pure
changelog commits are dropped.

Additional context from user: $ARGUMENTS

Read these first:

- `../../references/branch-scope.md`: a branch is not a release, base branch,
  changelog file lookup, whole-branch perspective.
- `../../references/entry-rules.md`: categorizing, format, voice, exclusions.
- `../../references/commit-message.md`: used in Phase 4.

Write entries and the commit message per `../../references/prose-rules.md`.

## Phase 1: Safety checks, scope, approval

1. **Preconditions.** Report why and stop if any fail:
   - Working tree dirty (`git status --porcelain` non-empty).
   - Detached HEAD, or an in-progress rebase, merge, or cherry-pick.
   - Currently on the base branch.

2. Detect the base and find the changelog file per `branch-scope.md`.

3. **Partition the branch's commits** that touch the changelog file:

   ```console
   $ git log origin/<base>..HEAD --format='%h %s' -- <changelog-file>
   ```

   - **Pure changelog commits** touch only the changelog file. Phase 2 drops
     them.
   - **Mixed commits** entangle changelog hunks with code. They cannot be
     dropped. Ask via `AskUserQuestion` per commit: leave it intact and let the
     new tip commit supersede its entries (recommended), or abort so the user
     can split it.
   - No changelog commits: nothing to rewrite. Suggest `/changelog` or
     `/changelog:refresh` and stop.

4. **Approve the rewrite.** Nothing in git changes before this approval,
   whether or not the branch was pushed. Via `AskUserQuestion`, show:
   - the commits Phase 2 will drop (SHA and subject);
   - the backup branch it will create first;
   - when the dropped commits are pushed (the branch exists on the remote),
     that the rewrite needs a later `git push --force-with-lease` by the
     user. This skill never pushes.

   Proceed only on an explicit yes. Otherwise stop with the tree unchanged.

## Phase 2: Back up and rebase out the old changelog commits

1. **Back up.** Record the current tip and create a backup branch, then report
   its name and SHA:

   ```
   git branch changelog-rewrite-backup-$(date -u +%Y%m%d-%H%M%SZ)
   ```

2. Drop the pure changelog commits non-interactively with a scripted sequence
   editor that turns their `pick` lines into `drop` by SHA. With GNU
   coreutils:

   ```
   GIT_SEQUENCE_EDITOR='sed -i -E "s/^pick (<sha1>|<sha2>)/drop \1/"' git rebase -i origin/<base>
   ```

   On BSD/Darwin, `-i` requires an explicit backup suffix; without the empty
   one it consumes `-E` as the suffix and litters the rebase directory:

   ```
   GIT_SEQUENCE_EDITOR='sed -i "" -E "s/^pick (<sha1>|<sha2>)/drop \1/"' git rebase -i origin/<base>
   ```

   Use each dropped commit's abbreviated SHA exactly as the todo list shows
   it. On conflict, stop and show the state; never resolve by discarding user
   code.

3. **Verify the invariant.**
   - Code unchanged: `git diff <backup> HEAD -- . ':(exclude)<changelog-file>'`
     must be empty. Intact mixed commits keep this true.
   - With only pure commits dropped and no mixed commits,
     `git diff origin/<base> HEAD -- <changelog-file>` must now be empty.

   If either check fails, restore with `git reset --hard <backup>`, report,
   and stop.

## Phase 3: Regenerate entries and present

Approval gate. Do not edit or commit before explicit approval.

Generate entries from the branch's current net change against
`origin/<base>`, per `entry-rules.md`. Entries superseding a mixed commit's
surviving changelog hunks may update those hunks, which are branch-owned, but
nothing from the base branch.

Present:

1. The summary line
   `Branch: <name> | Base: <base> | Dropped: <shas> | Backup: <branch>`.
2. The proposed entries as exact markdown, the insertion point, and the voice
   check and target line from `entry-rules.md`.
3. An `AskUserQuestion` with **Insert** and **Edit first** (return to
   generation). `--commit` alone decides what lands, so offer no commit
   choice: the rebase has already run, and a yes here would mean something
   different from the one a fresh commit needs.

## Phase 4: Insert, commit, report

Run only after the Phase 3 approval.

1. Apply with Edit. With `--commit` in `$ARGUMENTS`, commit once at the tip per
   `commit-message.md`. Without it, leave the edit uncommitted and show a
   ready-to-use commit message.
2. Report:
   - the backup branch, to delete once satisfied (`git branch -D <backup>`);
   - an uncommitted changelog edit awaiting the user's commit, when `--commit`
     was not passed;
   - for a pushed branch, that the user needs `git push --force-with-lease` to
     publish the rewrite.
