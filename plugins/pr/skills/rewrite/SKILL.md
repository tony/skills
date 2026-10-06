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
branch's PR; `/pr` handles branches without a PR. Fetch it (omit
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

The diff base is the PR's **`baseRefName`**, so a stacked PR diffs
against its parent branch, never against trunk. Gather the net change:

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

After the fetch in step 1 and before drafting, save the existing body
and title verbatim. Shell state does not persist, so this runs as one
script; it prints the backup directory, and every later command uses
that literal path. Take `<number>` from the JSON above:

```bash
d="$(git rev-parse --git-path pr-backups)/$(date -u +%Y%m%d-%H%M%SZ)-pr<number>"
mkdir -p "$d"
gh pr view <number> --json body --jq .body >"$d/body.md"
gh pr view <number> --json title --jq .title >"$d/title.txt"
printf '%s\n' "$d"
```

Tell the user the printed path. To restore:
`gh pr edit <number> --body-file <backup>/body.md`.

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
Without an interactive question tool, carry the item and flag it in the
proposal. A dropped item survives in the backup.

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

Output shape: one result line (the PR), the proposed title and full
body, the carried and dropped items, then the apply question. A run
that stops early is one sentence saying what happened and that nothing
changed, then what the user must do.

- Show the proposed title and full body.
- Summarize what was carried forward and what was dropped, with a
  one-line reason per drop, so the user can veto.
- Ask whether to apply. Without an interactive question tool, stop
  after showing the proposal; edit nothing. On approval, write the body
  to `body.new.md` in the printed backup directory and run:

  ```console
  $ gh pr edit <number> --title "..." --body-file <backup>/body.new.md
  ```

  An approval names this `gh pr edit` only, never a commit or push.

- Confirm with the PR URL and repeat the backup path.

## Rules

- **Back up first**: never call `gh pr edit` before the old body is on
  disk and its path reported.
- **Lose no context silently**: every item the diff cannot derive is
  carried, asked about, or listed as dropped at the presentation gate.
- **Never** force-push, push, or run destructive git commands; the only
  write is `gh pr edit` after approval.
