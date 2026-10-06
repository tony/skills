---
name: rewrite
description: "Use when an existing PR description should be rewritten from scratch against the branch's current net change, keeping context that still matters."
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
argument-hint: "[PR number or URL, and/or a template path or hint]"
user-invocable: true
disable-model-invocation: true
---

# Rewrite PR Description

Regenerate an existing PR's description from scratch. Where
`/pr:refresh` patches stale content inside the existing structure, this
skill discards the old structure and drafts a fresh description of the
branch's current net change, after mining the old description for
context worth carrying forward.

User input: $ARGUMENTS

## Procedure

### 1. Resolve the PR and its target

Use the PR number or URL in `$ARGUMENTS`; otherwise use the current
branch's PR. When none exists, report that and stop; `/pr` handles
branches without a PR. Fetch it (omit `<number>` for the current
branch's PR):

```bash
gh pr view <number> --json number,title,body,url,baseRefName,headRefName,state
```

The diff base is the PR's **`baseRefName`**, so a stacked PR diffs
against its parent branch, never against trunk. Gather the net change:

```bash
git fetch origin <baseRefName>
```

```bash
git log origin/<baseRefName>..HEAD --oneline
```

```bash
git diff origin/<baseRefName>...HEAD --stat
```

```bash
git diff origin/<baseRefName>...HEAD
```

### 2. Back up the current description

Save the existing body and title verbatim before drafting:

```bash
mkdir -p .git/pr-backups/$(date -u +%Y%m%d-%H%M%SZ)-pr<number>
```

Write `body.md` and `title.txt` there and tell the user the path. To
restore: `gh pr edit <number> --body-file <backup>/body.md`.

### 3. Mine the old description for context

Inventory everything in the body the diff cannot derive:

- Issue keywords and links (`Fixes #N`, `Closes #N`), companion PR
  links, tracking issues
- Setup-required steps, deployment or rollout notes
- Screenshots, recordings, benchmark numbers, external links
- Reviewer commitments, @-mentions, unchecked test-plan items
- Hand-written rationale absent from the commit messages

Classify each item as **carry forward** (still applies), **drop**
(obsolete given the current diff), or **unclear**. For unclear items,
ask through `AskUserQuestion`: quote the item and offer carry or drop.
A dropped item survives in the backup.

### 4. Resolve the template

Follow `../../references/template-resolution.md`.

### 5. Draft the new description

Follow the drafting rules in `../pr/SKILL.md`, section *Draft the
description*: its title, section, table, and proportionality patterns,
and its *What NOT to include* list. Write it per
`../../references/prose-rules.md`. Then:

- Weave each carry-forward item from step 3 into its place in the new
  structure.
- Describe the branch's **current net change** only; the old
  description's framing of superseded approaches does not carry over.

### 6. Present and apply

- Show the proposed title and full body.
- Summarize what was carried forward and what was dropped, with a
  one-line reason per drop, so the user can veto.
- Ask whether to apply. On approval, write the body to `body.new.md` in
  the backup directory and run:

  ```bash
  gh pr edit <number> --title "..." --body-file <backup>/body.new.md
  ```

- Confirm with the PR URL and repeat the backup path.

## Rules

- **Back up first**: never call `gh pr edit` before the old body is on
  disk and its path reported.
- **Lose no context silently**: every item the diff cannot derive is
  carried, asked about, or listed as dropped at the presentation gate.
- **Never** force-push, push, or run destructive git commands; the only
  write is `gh pr edit` after approval.
