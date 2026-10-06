---
name: pr
description: >-
  Use when drafting a pull request description from the current branch's
  diff, optionally creating the PR with gh.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
metadata:
  argument-hint: "[optional hint about the PR, e.g. 'fixes the race condition']"
  source: "plugins/pr/skills/pr/SKILL.md"
---

# Generate PR Description

Draft a pull request description from the current branch's diff.

User hint: $ARGUMENTS

## Procedure

### 1. Gather context

Follow `references/branch-context.md` to find the base and gather the branch's change.

Review the diff and **all** commits, not only the latest.
Determine the kind of change (feature, fix, refactor, CI, docs), the
modules it touches, and whether it is a small targeted fix or a large
multi-module change.

### 2. Read project conventions

- Read `AGENTS.md` and `CLAUDE.md` for PR description conventions.
- Resolve the PR template per `references/template-resolution.md`.
  When several candidate templates are in play, ask; never guess. A
  template's structure is the starting point; fill it with the patterns
  below.

### 3. Draft the description

Write it per `references/prose-rules.md`.

#### Title

- Under 70 characters
- Describe the impact, not the implementation
- Match the project's commit and PR title style if one exists

#### Body

Use only the sections that fit the change, in proportion to the diff: a one-file fix needs few; a 30-file feature needs more than one sentence.

**`## Summary`** — 3-7 bullet points:
- Each bullet opens with a **bold impact label** (**Fix**, **Add**, **Remove**, **Replace**, **Migrate**)
- A reviewer should understand the full scope from the summary alone
- For non-trivial changes, include the motivation

**`## Changes`** or **`## Changes by area`** — for multi-module changes:
- Group by area with `###` sub-headings
- Use **bold file/module names** with inline descriptions, e.g. **`src/server.py`**: Wrap post-deletion code in `try/finally` for safe env restoration

**`## Design decisions`** — when trade-offs were made:
- Explain rationale with **bold-label** entries, including "why not" for alternatives weighed
- Omit the section when no alternative was weighed; never invent one or speculate about future needs

**`## Verification`** — copyable commands proving completeness:
- Each `rg` or `grep` command in its own code block, returning zero matches for removed patterns or expected matches for added ones

**`## Test plan`** — a checklist; mark `- [x]` only for what you ran this session and `- [ ]` for the rest:
- Each item says what is validated, not just the command
- Include the project's test/lint/typecheck commands and specific test names when they exist
- For removal or migration PRs, add "verify zero matches for X" items

**`## Setup Required`** — pre-merge steps with external URLs (only when applicable)

**`## Companion PR`** — links to related PRs in other repositories (only when applicable)

Use a table only for matrix-shaped data: flag maps, old-to-new renames, environment matrices, before/after comparisons.

Do not hard-wrap body text: GitHub renders it as Markdown, and hard wraps break paragraphs mid-sentence. Write each paragraph and bullet as one line.

One command per code block, explanation outside it, no `#` comments inside. For behavioral or UX changes, show before and after in separate labeled code blocks.

#### What NOT to include

- Test counts or passing numbers ("875 tests pass")
- Git SHAs, file-level line numbers, counts of files or lines changed
- Details the reviewer can see in the diff or `git log`
- An invented issue link. Write `Fixes #N` only for an issue number the user, the branch name, or a commit supplied. (The merge commit title takes ` (#N)`; see the merge-commit skill.)
- Within-branch tactical narrative: renames of unshipped symbols, "no longer X" / "previously Y", diff paraphrases, or `### Fixes` framing for behavior that never shipped. Keep such text only when a user of the latest published release experienced the old name, behavior, or bug.

Describe the branch's net shipped result, not its evolution: ignore fixups, reverts-then-re-adds, and WIP states.

### 4. Present and Create

Output the proposed title and full body, then one question. The chat text around the body is plain prose with no bold labels, and never asks for an issue number.

Reply in this shape, as plain text outside any code fence, with plain bullets and no bold (never `- **Label:** ...`):

````text
Draft for the 2 commits on fix/metrics-race not on origin/main.
Ran the project's tests: pass.

Title: metrics(fix[counter]) Stop losing hits under concurrent requests

```markdown
## Summary

- **Fix** a race in `Counter.record()` that dropped concurrent hits.

## Test plan

- [x] Concurrent calls to `record()` add up with no lost counts
- [ ] Full suite in CI
```

Create the PR with gh pr create, or only output the description?
````

- Ask whether to create the PR via `gh pr create` or only output the description.
- Without an interactive question tool, output the description and stop. A request that says to create the PR authorizes `gh pr create` and the push it needs, nothing else.
- To create: push the branch with `git push -u origin <branch>` if it is not pushed, never to `main` or `master`, and pass the body through a heredoc:

  ```bash
  gh pr create --title "the title" --body "$(cat <<'EOF'
  ## Summary
  ...
  EOF
  )"
  ```

- When `gh` is missing or unauthenticated, stop: say the PR was not created and name the fix (`gh auth login`); the drafted description stays valid.
- Return the PR URL when done.

A run that stops early (empty log, no base, `gh` failure) is one sentence saying what happened and that nothing changed, then what the user must do.

---

## Rules

Never force-push, run destructive git commands, or push to `main` or `master`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
