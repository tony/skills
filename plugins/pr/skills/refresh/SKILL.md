---
name: refresh
description: "Use when an existing PR description has gone stale and must match the branch's current net change, keeping its structure and hand-written text."
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
argument-hint: "[PR number or URL, and/or a hint, e.g. 'the retry logic was dropped']"
user-invocable: true
disable-model-invocation: true
---

# Refresh PR Description

Bring an existing PR description back in sync with what the branch
**currently** does, non-destructively. Structure, formatting, links, and
hand-written customizations stay; only content the branch's evolution
made stale changes. Write the updated text per
`../../references/prose-rules.md`.

This skill is **content-only**. It never restructures the description,
applies a template, or discusses structure or templates. When the user
asks for a different structure or names a template, reply in one line
that `/pr:rewrite` restructures, then continue the content-only refresh
(or stop, if restructuring was the only request).

User input: $ARGUMENTS

## Procedure

### 1. Resolve the PR and its target

Use the PR number or URL in `$ARGUMENTS`; otherwise use the current
branch's PR. Fetch it (omit
`<number>` for the current branch's PR):

```console
$ gh pr view <number> --json number,title,body,url,baseRefName,headRefName,state
```

When `gh` is missing, unauthenticated, or finds no PR, stop: say what
failed, name the fix (`gh auth login`, or the PR number to pass), and
change nothing.

Compare `headRefName` with `git branch --show-current`. On a mismatch,
or a detached HEAD, stop: the diff would describe another branch. Say
the PR's head branch is not checked out and name `headRefName`; change
nothing.

The diff base is the PR's **`baseRefName`**, so a PR stacked on a
sibling branch diffs against that branch, never against trunk. Gather
the net change:

```console
$ git fetch origin <baseRefName>
```

```console
$ git log origin/<baseRefName>..HEAD --oneline
```

```console
$ git diff origin/<baseRefName>...HEAD --stat
```

```console
$ git diff origin/<baseRefName>...HEAD
```

### 2. Back up the current description

After the fetch in step 1 and before mapping or drafting, save the
existing body and title verbatim. Shell state does not persist, so this
runs as one script; it prints the backup directory, and every later
command uses that literal path. Take `<number>` from the JSON above:

```bash
d="$(git rev-parse --git-path pr-backups)/$(date -u +%Y%m%d-%H%M%SZ)-pr<number>"
mkdir -p "$d"
gh pr view <number> --json body --jq .body >"$d/body.md"
gh pr view <number> --json title --jq .title >"$d/title.txt"
printf '%s\n' "$d"
```

Tell the user the printed path. To restore:
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
ask through `AskUserQuestion`: quote the text and offer keep as-is,
update (with the proposed replacement), or remove. Batch related
uncertainties into one question set. Never resolve ambiguity by
guessing. Without an interactive question tool, keep the text as-is and
list each uncertainty in the proposal.

### 5. Present and apply

Output shape: one result line (the PR and the sections that change),
the old → new comparison, then the apply question. A run that stops
early is one sentence saying what happened and that nothing changed,
then what the user must do.

- Show the proposed edit as an old → new comparison of the changing
  sections only, and state which sections are untouched.
- Update the title only when it is factually stale; keep its style.
- Ask whether to apply. Without an interactive question tool, stop
  after showing the proposal; edit nothing. On approval, write the new
  body to `body.new.md` in the printed backup directory, so formatting
  survives shell quoting, then run:

  ```console
  $ gh pr edit <number> --body-file <backup>/body.new.md
  ```

  An approval names this `gh pr edit` only, never a commit or push.

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
