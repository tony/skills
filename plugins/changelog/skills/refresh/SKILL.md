---
name: refresh
description: Update the branch's own changelog entries to match its current net change; commits only with --commit
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "[--commit] [optional additional context about the changes]"
user-invocable: true
disable-model-invocation: true
---

# Refresh Changelog Entries

Bring the changelog entries this branch introduced back in sync with what the
branch does now. With `--commit`, the correction lands as a new commit on top;
otherwise the edit stays uncommitted for the user to commit. History is never
rewritten; `/changelog:rewrite-aggressively` does that.

Scope: edit only changelog content the branch added. Entries from the base
branch, whether earlier releases or other work's unreleased entries, are
read-only. A correction that needs a line the branch did not add: ask, or without a
question tool leave it and note the limitation.

Additional context from user: $ARGUMENTS

Read these first:

- `../../references/branch-scope.md`: a branch is not a release, base branch,
  changelog file lookup, whole-branch perspective.
- `../../references/entry-rules.md`: categorizing, format, voice, exclusions.
- `../../references/commit-message.md`: used in Phase 4.

Write entries and the commit message per `../../references/prose-rules.md`.

## Phase 1: Establish scope

1. Detect the base and find the changelog file per `branch-scope.md`. No
   changelog changes on this branch and no changelog file: suggest
   `/changelog:changelog` and stop.
2. Extract the branch's changelog footprint. The added lines are the
   branch-owned entries, the only region this skill may edit:

   ```console
   $ git diff origin/<base>...HEAD -- <changelog-file>
   ```

3. List the branch commits that touch the file (with no `origin` remote,
   substitute the local base name for `origin/<base>` in these commands):

   ```console
   $ git log origin/<base>..HEAD --oneline -- <changelog-file>
   ```

   None: say so and offer the `/changelog:changelog` procedure instead.

4. Check the changelog is clean per `commit-message.md`; when it is not, edit
   only and say why.

## Phase 2: Recompute what the entries should say

Apply `branch-scope.md` and `entry-rules.md`: read conventions, categorize, and
generate the entries the branch should have from its current net change
(`git log origin/<base>..HEAD` and `git diff origin/<base>...HEAD`, three-dot,
so base commits the fetch pulled in stay out). For the PR number, run
`gh pr view --json number --jq .number`; on failure write `(#???)`. Never copy
a number from a dropped or stale entry.

## Phase 3: Diff documented vs. actual

Compare the branch-owned entries against the recomputed ones.

- **Accurate**: leave byte-for-byte untouched, including phrasing you would
  have written differently. Refresh fixes drift, not style.
- **Stale**: the entry describes something the branch no longer does, or
  misstates scope. Rewrite it in place, matching the file's style.
- **Missing**: a user-visible change with no entry. Insert it in the correct
  section of the unreleased block, following the section-order rules.
- **Orphaned**: the entry's change left the branch. Remove the entry.
- **Out of reach**: the fix would touch content the branch did not add (the
  branch's entry merged into a pre-existing bullet, or a section heading
  shared with base entries must change). Ask via `AskUserQuestion` first; if
  declined, or without a question tool, leave it and note the limitation.

## Phase 4: Present, edit, commit

Approval gate. Do not edit or commit without approval. Approval comes from,
in order:

- `--commit` in `$ARGUMENTS`: approves the edit and the commit.
- An invoking message that asks to refresh, update, or fix the entries:
  approves the edit only.
- `AskUserQuestion`, when the host has it and neither of the above applies.
- Otherwise, present the proposal and stop; never wait for a reply.

1. Present the summary line
   (`Branch: <name> | Base: <base> | Changelog commits: <count>`), the proposed
   old to new markdown for each touched entry, the statement that everything
   else in the file is untouched, the voice check and `Target` line from
   `entry-rules.md`, and `Notes` only for a fact the user must act on, such as
   an out-of-reach correction left undone. Never recap checks that passed.
   Refer to commits by subject in prose, never by bare SHA. Close with the
   question, or when stopping, one line: nothing was edited; re-run with
   "refresh the entries" to edit only, or with `--commit` to apply and commit.

   When every entry is accurate, send the no-change shape instead: the
   summary line, one result sentence, and `Notes` only for out-of-reach items
   left undone. No Old/New, voice check, `Target` line, or re-run line.

   ```text
   Branch: feat/cache-evict | Base: main | Changelog commits: 2

   The branch's entries already match; nothing to change.

   Notes:
   - The "Cache" heading is shared with base entries; renaming it is left undone and needs your approval.
   ```

   Omit `Notes` when nothing was left undone. Each Notes bullet names what
   was left undone and that it needs the user's approval; no alternatives or
   offers beyond that.

   Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

   ```text
   Branch: feat/cache-evict | Base: main | Changelog commits: 2

   Old:
   - Add `Cache.evict()` (#212)

   New:
   - Add `Cache.evict()` to drop a cached key (#212)

   Everything else in CHANGES.md is untouched.

   Voice check:
   - Add `Cache.evict()` to drop a cached key: can I take a new affordance?

   Target: CHANGES.md, Unreleased, Features, after the "### Features" heading. No version assigned, no release cut.

   Notes:
   - The "Cache" heading is shared with base entries; renaming it needs your say-so.
   ```

2. On approval, apply with Edit, confined to the branch's footprint plus
   approved insertions in the unreleased block.
3. Show the modified region. Then check the scope guard: run
   `git diff origin/<base>...HEAD -- <changelog-file>` for the committed
   footprint and `git diff -- <changelog-file>` for the edit; the edit must
   touch no line outside the Phase 1 footprint and the approved insertions.
4. With `--commit` in `$ARGUMENTS`, commit the edit as one new commit on top,
   per `commit-message.md`: no `Co-Authored-By`, no "Generated with" or other
   tool trailer, no emoji. Otherwise leave it uncommitted and show a
   ready-to-use commit message.

Never rebase, amend, or force-push.
