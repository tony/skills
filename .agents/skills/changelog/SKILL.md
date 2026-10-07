---
name: changelog
description: >-
  Generate CHANGES entries from branch commits and PR context
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[--commit] [optional additional context about the changes]"
  source: "plugins/changelog/skills/changelog/SKILL.md"
---

# Changelog Entry Generator

Generate changelog entries from the current branch's commits and PR context,
and insert them into the changelog file after user review.

Additional context from user: $ARGUMENTS

Read these first:

- `references/branch-scope.md`: a branch is not a release, base branch,
  changelog file lookup.
- `references/entry-rules.md`: categorizing, format, voice, exclusions.
- `references/commit-message.md`: used in Phase 4 and 5.

Write entries and the commit message per `references/prose-rules.md`.

## Phase 1: Gather Context

1. **Read project conventions** per `entry-rules.md`.
2. **Detect the base branch** per `branch-scope.md`. Stop if on it.
3. **Find and read the changelog file** per `branch-scope.md`.
4. **Analyze its format.** The existing file is the source of truth:
   - Release heading pattern (`## v1.2.3`, `## [1.2.3]`, `## project v1.2.3`,
     `## 1.2.3 (YYYY-MM-DD)`).
   - Unreleased section: a heading or a placeholder comment
     (`<!-- END PLACEHOLDER`, `## [Unreleased]`, `## Unreleased`).
   - Insertion point: after a placeholder, under an unreleased heading, or at
     the top. Never under a versioned heading. If the topmost heading is a
     release, entries go above it in an unreleased block; ask the user for
     the project's wording, or without a question tool propose
     `## Unreleased` and flag it as a guess.
   - Section names, order, and capitalization of the most recent populated
     release.
   - Entry shape and typical length.
5. **Check for a PR.** `gh pr view --json number,title,body,labels` returns the
   number, title, body, and labels. A failure means no PR; use `(#???)`
   placeholders.
6. **Check the changelog is clean.** `git status --porcelain -- <changelog-file>`
   output means earlier uncommitted edits: a commit would sweep them in, so
   never commit; insert only, and say why.
7. **Get commits.** Fetch per `branch-scope.md` first. `git log origin/<base>..HEAD --format='%H %s%n%b---'`
   gives subjects and bodies. No commits ahead: report "No commits ahead of
   the base branch" and stop.

## Phase 2: Categorize and Generate

Categorize and group the commits, then write the exact markdown to insert,
both per `entry-rules.md`. Keep each entry's source commits for traceability.

## Phase 3: Present for Review

Approval gate. Do not edit before approval. Approval comes from, in order:

- `--commit` in `$ARGUMENTS`: approves the insert and the commit.
- An invoking message that asks to add or insert the entries ("go ahead and
  add them"): approves insert only.
- `ask-user-choice`, when the host has it and neither of the above applies.
- Otherwise, present the proposal and stop; never wait for a reply.

Present, in this order:

1. Summary line: `Branch: <branch-name> | Commits: <count> | PR: #<number> (or "none")`.
2. The proposed entries in a fenced `markdown` block, showing the exact text.
3. The voice check and target line from `entry-rules.md`.
4. The commit message the entries would land under, built per
   `commit-message.md`.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

````text
Branch: feat/cache-evict | Commits: 3 | PR: #212

```markdown
- Add `Cache.evict()` to drop a cached key (#212)
```

Voice check:
- Add `Cache.evict()` to drop a cached key: can I take a new affordance?

Target: CHANGES.md, Unreleased, Features, after the "### Features" heading. No version assigned, no release cut.

Commit message: docs(CHANGES) Cache key eviction

Notes:
- Left the get() empty-value fix out: no release shipped that bug.
````

When asking, use `ask-user-choice`: "Insert into `<changelog-file>`?" Offer:
   - **Insert only**: apply the edit and leave it uncommitted.
   - **Insert and commit**: apply the edit and commit the changelog file with
     the message shown.
   - **Edit first**: return to Phase 2.

Without approval already given and without `ask-user-choice`, end with one
line: nothing was edited; re-run with "add the entries" to insert, or with
`--commit` to insert and commit. Name no temp files or local paths.

A stopped run (no commits ahead, on the base branch) is one result sentence,
then what the user needs to do.

## Phase 4: Insert into Changelog

Run only after approval. Without `--commit` or an explicit "commit" choice,
never commit.

1. Insert at the Phase 1 insertion point with Edit, matching the file's
   blank-line spacing. Leave every release heading and version file
   untouched, unless the user explicitly asked to cut a release.
2. Merge into the unreleased block:
   - Append to an existing section heading there, before the next `###` or
     `## ` heading. Never duplicate a heading.
   - Insert a new section in the section order from `entry-rules.md`.
3. Read the modified region back and show it.
4. Commit only if Phase 3 chose it, per `commit-message.md`, once, with the
   message already shown: no `Co-Authored-By`, no "Generated with" or other
   tool trailer, no emoji. Otherwise say the edit is uncommitted and give the
   commit as one `console` command with the message, so committing is one paste.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold, and no local paths:

````text
Inserted 1 entry into CHANGES.md under Unreleased; it is uncommitted.

```markdown
### Features

- Add `Cache.evict()` to drop a cached key (#212)
```

To commit it, run:

```console
$ git commit \
    --message "docs(CHANGES) Cache key eviction" \
    -- CHANGES.md
```
````


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
