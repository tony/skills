---
name: pr-refresh
description: >-
  Use when an existing PR description has gone stale and must match the
  branch's current net change, keeping its structure and hand-written text.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[PR number or URL, and/or a hint, e.g. 'the retry logic was dropped']"
  source: "plugins/pr/skills/refresh/SKILL.md"
---

# Refresh PR Description

Bring an existing PR description back in sync with what the branch
**currently** does, non-destructively. Structure, formatting, links, and
hand-written customizations stay; only content the branch's evolution
made stale changes. Write the updated text per
`references/prose-rules.md`.

This skill is **content-only**. It never restructures the description,
applies a template, or discusses structure or templates. When the user
asks for a different structure or names a template, reply in one line
that the `pr-rewrite` skill restructures, then continue the content-only refresh
(or stop, if restructuring was the only request).

User input: $ARGUMENTS

## Procedure

### 1. Resolve the PR and its target

Use the PR number or URL in `$ARGUMENTS`; otherwise use the current
branch's PR. When none exists, report that and stop. Fetch it (omit
`<number>` for the current branch's PR):

```bash
gh pr view <number> --json number,title,body,url,baseRefName,headRefName,state
```

The diff base is the PR's **`baseRefName`**, so a PR stacked on a
sibling branch diffs against that branch, never against trunk. Gather
the net change:

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

Before any analysis, save the existing body verbatim:

```bash
mkdir -p .git/pr-backups/$(date -u +%Y%m%d-%H%M%SZ)-pr<number>
```

Write the body to `body.md` and the title to `title.txt` in that
directory, and tell the user the path. To restore:
`gh pr edit <number> --body-file <backup>/body.md`.

### 3. Map the description against the current diff

Read the body section by section and classify every claim:

- **Still accurate**: the net diff still does it. Leave it
  byte-for-byte untouched, including phrasing you would have written
  differently. Refresh fixes staleness, not style.
- **Stale**: describes behavior, files, flags, or approaches the branch
  no longer contains, or misstates what it now does. Rewrite minimally,
  in the section's voice and format.
- **Missing**: a change in the net diff the description omits. Add it to
  the section where it belongs, matching that section's format. Never
  create a section for it.
- **Unverifiable**: hand-written content the diff cannot confirm:
  reviewer commitments, deployment notes, screenshots, benchmark
  numbers, external links, checked task-list items. **Preserve by
  default.** When the diff suggests one is now wrong (a screenshot of a
  UI the branch has since changed), ask before touching it.

Preserve section order and headings, link targets and text, images,
badges, HTML comments, task-list check states, issue keywords
(`Fixes #N`), and @-mentions.

### 4. Ambiguity gate

When it is unclear whether existing content is stale or load-bearing,
ask through `ask-user-choice`: quote the text and offer keep as-is,
update (with the proposed replacement), or remove. Batch related
uncertainties into one question set. Never resolve ambiguity by
guessing.

### 5. Present and apply

- Show the proposed edit as an old → new comparison of the changing
  sections only, and state which sections are untouched.
- Update the title only when it is factually stale; keep its style.
- Ask whether to apply. On approval, write the new body to `body.new.md`
  in the backup directory, so formatting survives shell quoting, then
  run:

  ```bash
  gh pr edit <number> --body-file <backup>/body.new.md
  ```

- Confirm with the PR URL and repeat the backup path.

## Rules

- **Back up first**: every run saves the body before editing; the
  smallest edit that restores accuracy wins.
- **Content-only**: never add, remove, rename, or reorder sections.
- **Describe the net result** against the base, never the branch's
  internal history, and add no test counts, SHAs, line numbers, or
  file-changed counts.
- **Never** force-push, push, or run destructive git commands; the only
  write is `gh pr edit` after approval.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
