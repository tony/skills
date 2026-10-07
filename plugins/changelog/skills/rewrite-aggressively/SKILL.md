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
entries from the branch's current net change. With `--commit`, the entries
land as one fresh commit at the tip; otherwise they stay an uncommitted edit.
`/changelog:refresh` stacks a correcting commit instead.

Scope: only the branch's own changelog content is rewritten. Base-branch
changelog content and code history are never modified; only pure changelog
commits are dropped.

Additional context from user: $ARGUMENTS

Read these first:

- `../../references/branch-scope.md`: a branch is not a release, base branch,
  changelog file lookup, whole-branch perspective.
- `../../references/entry-rules.md`: categorizing, format, voice, exclusions.
- `../../references/commit-message.md`: used in Phase 4.

Write entries and the commit message per `../../references/prose-rules.md`.

## Phase 1: Safety checks, scope, approval

1. **Detect the base**, fetch it, and find the changelog file per
   `branch-scope.md`.

2. **Preconditions.** Report why and stop if any fail. Name the failed
   precondition in plain words; mention no local paths or temp directories:
   - Working tree dirty (`git status --porcelain` non-empty). Tell the user to
     commit or stash the tracked changes. Advise `git stash -u` for untracked
     files only after `git rev-parse --show-toplevel` shows a root that is
     neither the output of `cd ~ && pwd -P` nor a parent of it (compare
     physical paths, not the string `$HOME`).
   - Detached HEAD, or an in-progress rebase, merge, or cherry-pick.
   - Currently on the base branch.
   - A merge commit between the base and HEAD (`git rev-list --merges
     origin/<base>..HEAD` non-empty): the rebase would flatten it.

   Reply in this shape for a stopped run, as plain text outside any code
   fence: one result sentence, then what the user must do. Skip the checks that
   passed.

   ```text
   Stopped before changing anything: the working tree has uncommitted changes in src/ping.py.

   Commit or stash them, then run /changelog:rewrite-aggressively --commit again.
   ```

3. **Partition the branch's commits** that touch the changelog file:

   ```console
   $ git log origin/<base>..HEAD --format='%h %s' -- <changelog-file>
   ```

   Classify each by the files it touches:

   ```console
   $ git show --name-only --format= <sha>
   ```

   - **Pure changelog commits** touch only the changelog file. Phase 2 drops
     them.
   - **Mixed commits** entangle changelog hunks with code and cannot be
     dropped. Ask via `AskUserQuestion` per commit: leave it intact and let the
     new tip commit supersede its entries (recommended), or abort so the user
     can split it. Without a question tool, leave it intact and say so.
   - No changelog commits: nothing to rewrite. Suggest `/changelog:changelog`
     or `/changelog:refresh` and stop.

4. **Approve the rewrite.** Nothing in git changes before this approval.
   `--commit` does not approve the rewrite, and neither does an invoking
   request to "rewrite" or "clean up" the changelog; only explicit approval of
   the history rewrite itself does (for example "yes, drop those commits").
   Via `AskUserQuestion`, or in the invoking message when the host has no such
   tool, show:
   - the commits Phase 2 will drop, by subject, never by bare SHA;
   - the backup branch it will create first, named
     `changelog-rewrite-backup-` plus the current UTC date and time;
   - that a failed invariant check restores the backup with
     `git reset --hard`;
   - when the dropped commits are pushed, that publishing needs a later
     `git push --force-with-lease --force-if-includes` by the user. This skill
     never pushes.

   Proceed only on an explicit yes. Without one (including with no
   `AskUserQuestion` and no approval in the message), stop with the list above
   and the tree unchanged; never wait.

   Reply in this shape for the approval stop, as plain text outside any code
   fence, with plain bullets, no bold, and no recap of the checks that passed:

   ```text
   Nothing changed yet: the rewrite needs your explicit approval, and --commit does not count.

   If you approve:
   - The commit "docs(CHANGES) First draft of the cache entry" is dropped.
   - A backup branch, changelog-rewrite-backup-20261006-142530Z, is created first.
   - A failed check restores the backup.
   - The new entries are committed once at the tip.

   Reply "yes, drop that commit" to proceed.
   ```

## Phase 2: Back up and rebase out the old changelog commits

1. **Back up.** Create the backup branch and print its name, its tip SHA, and
   the merge-base with the base. Use these printed values literally in later
   commands:

   ```bash
   name="changelog-rewrite-backup-$(date -u +%Y%m%d-%H%M%SZ)"
   git branch "$name"
   echo "$name $(git rev-parse HEAD) $(git merge-base origin/<base> HEAD)"
   ```

2. Drop the pure changelog commits non-interactively with a scripted sequence
   editor that turns their `pick` lines into `drop` by SHA. Rebase onto the
   merge-base, not onto `origin/<base>`: the fetch may have moved the base, and
   the rebase must not also move code onto it. With GNU coreutils:

   ```console
   $ GIT_SEQUENCE_EDITOR='sed -i -E "s/^pick (<sha1>|<sha2>)/drop \1/"' git rebase -i <merge-base>
   ```

   On BSD/Darwin, `-i` needs an explicit (here empty) suffix:

   ```console
   $ GIT_SEQUENCE_EDITOR='sed -i "" -E "s/^pick (<sha1>|<sha2>)/drop \1/"' git rebase -i <merge-base>
   ```

   Use each dropped commit's abbreviated SHA exactly as the todo list shows
   it. On conflict, run `git rebase --abort` and confirm `git rev-parse HEAD`
   equals the backup tip printed in step 1; if it does not, run
   `git reset --hard <backup>`. Report the backup name and stop; never resolve
   by discarding user code.

3. **Verify the invariant.**
   - Code unchanged: `git diff <backup> HEAD -- . ':(exclude)<changelog-file>'`
     must be empty. Intact mixed commits keep this true.
   - With only pure commits dropped and no mixed commits,
     `git diff <merge-base> HEAD -- <changelog-file>` must now be empty.

   If either check fails, restore with `git reset --hard <backup>`, report,
   and stop.

## Phase 3: Regenerate entries and present

Approval gate. The Phase 1 approval covers the rebase only. Approval to
edit comes from, in order:

- `--commit` in `$ARGUMENTS`: approves the edit and the commit.
- An invoking message that asks to insert or regenerate the entries: approves
  the edit only.
- `AskUserQuestion`, when the host has it and neither of the above applies.
- Otherwise, present the entries and stop; never wait. The tree then holds
  the rebased history with no entries; say so and name the backup.

Generate entries from the branch's current net change
(`git diff origin/<base>...HEAD`, three-dot, so base commits the fetch pulled
in stay out), per `entry-rules.md`. For the PR number, run
`gh pr view --json number --jq .number`. On failure, if the branch already
merged, read the number from its merge commit on the base branch ("Merge pull
request #N"); otherwise write `(#???)`. Never copy a number from a dropped
commit or an earlier entry. Entries superseding a mixed commit's
surviving changelog hunks may update those hunks, which are branch-owned, but
nothing from the base branch.

When the edit was approved up front (`--commit` or an invoking request), skip
the Phase 3 reply and send only the Phase 4 reply.

Present:

1. The summary line
   `Branch: <name> | Base: <base> | Dropped: <count> | Backup: <branch>`.
2. The proposed entries as exact markdown, then the voice check and `Target`
   line from `entry-rules.md`.
3. When asking, an `AskUserQuestion` with **Insert** and **Edit first** (return
   to generation). Offer no commit choice: `--commit` alone decides what lands.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Branch: feat/cache-evict | Base: main | Dropped: 3 | Backup: changelog-rewrite-backup-20261006-142530Z

```markdown
- Add `Cache.evict()` to drop a cached key (#212)
```

Voice check:
- Add `Cache.evict()` to drop a cached key: can I take a new affordance?

Target: CHANGES.md, Unreleased, Features, after the "### Features" heading. No version assigned, no release cut.
```

## Phase 4: Insert, commit, report

Run only after the Phase 3 approval.

1. Apply with Edit. With `--commit` in `$ARGUMENTS`, commit once at the tip per
   `commit-message.md` (the project's own subject format wins): no `Co-Authored-By`, no "Generated with" or other tool
   trailer, no emoji. Without it, leave the edit uncommitted and show a
   ready-to-use commit message.
2. Report the backup branch (to delete once satisfied with
   `git branch -D <backup>`), an uncommitted edit awaiting the user's commit
   when `--commit` was not passed, and for a pushed branch the
   `git push --force-with-lease --force-if-includes` the user needs.

   Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Backup:** ...`), and no local paths. The subject line below is the no-convention form. Notes hold facts the user must act on, so never recap checks that passed and never compare the new subject with a dropped commit's:

   ````text
   Rewrote the changelog history of feat/cache-evict: 3 commits dropped, 1 added.

   ```markdown
   - Add `Cache.evict()` to drop a cached key (#212)
   ```

   Voice check:
   - Add `Cache.evict()` to drop a cached key: can I take a new affordance?

   Target: CHANGES.md, Unreleased, Features, after the "### Features" heading. No version assigned, no release cut.

   - Backup: changelog-rewrite-backup-20261006-142530Z; delete it once satisfied.
   - The entry is committed at the tip as docs(CHANGES) Cache key eviction.
   - The branch is pushed; publish with git push --force-with-lease --force-if-includes.
   ````
