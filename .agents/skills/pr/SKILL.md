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

Find the trunk without touching the network:

```console
$ git symbolic-ref --short refs/remotes/origin/HEAD
```

It prints `origin/<trunk>`; that is the base. When it fails, use the
first of `origin/main` or `origin/master` that
`git rev-parse --verify --quiet` accepts; when neither exists, ask the
user for the base, or stop and name the missing base when you cannot
ask. The local `origin/<trunk>` may be stale; run `git fetch origin
<trunk>` first when the user wants it current. Shell variables do not
survive between commands, so write the literal `origin/<trunk>` in each
command below. Gather the branch's change:

```console
$ git branch --show-current
```

```console
$ git log origin/<trunk>..HEAD --oneline
```

```console
$ git diff origin/<trunk>...HEAD --stat
```

```console
$ git diff origin/<trunk>...HEAD
```

An empty log means the branch has nothing ahead of the base; say so and
stop. Review the diff and **all** commits, not only the latest.
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
- Describe the impact, not the implementation; details belong in the body
- Match the project's commit and PR title style if one exists

#### Body

Use only the sections that fit the change, in proportion to the diff: a one-file fix needs few; a 30-file feature needs more than one sentence.

**`## Summary`** — 3-7 bullet points:
- Each bullet opens with a **bold impact label** (e.g., **Fix**, **Add**, **Remove**, **Replace**, **Migrate**)
- Concise but complete — a reviewer should understand the full scope from just the summary
- For non-trivial changes, include the motivation (why this change is needed)

**`## Changes`** or **`## Changes by area`** — for multi-module changes:
- Group by area with `###` sub-headings
- Use **bold file/module names** with inline descriptions
- Example: **`src/server.py`**: Wrap post-deletion code in `try/finally` for safe env restoration

**`## Design decisions`** — when trade-offs were made:
- Explain rationale with **bold-label** entries
- Include "why not" for alternatives considered
- Omit the section when no alternative was weighed; never invent an alternative or speculate about future needs
- Example: **Errors as values, not exceptions**: `SyncResult` follows the structured result pattern because...

**`## Verification`** — copyable commands proving completeness:
- Each `rg` or `grep` command on its own line in its own code block
- Commands should return zero matches for removed patterns or expected matches for added patterns
- Example: verify no f-strings remain in log calls

**`## Test plan`** — a checklist; mark `- [x]` only for what you ran this session and `- [ ]` for the rest:
- Each item describes **what is validated**, not just the command
- Include project test/lint/typecheck commands as discovered from AGENTS.md
- Include specific test names when they exist
- Example: `- [x] test_new_session_empty_stdout — verifies error on empty stdout`

**`## Setup Required`** — pre-merge steps (only when applicable):
- Numbered external URLs
- Specific configuration steps

**`## Companion PR`** — cross-repo links (only when applicable):
- Link to related PRs in other repositories

#### Tables

Use a table only for matrix-shaped data: parameter or flag maps,
old-to-new renames, environment matrices, sync/async pairs, or
before/after comparisons. Prefer prose or a list otherwise.

#### Line wrapping

**Do NOT hard-wrap PR body text.** Unlike commit messages, PR descriptions
are rendered as Markdown on GitHub — long lines reflow into paragraphs.
Hard-wrapping at 72 characters creates jarring mid-sentence line breaks
in the rendered view. Write prose and bullet text as single long lines;
let the editor/renderer handle display wrapping.

#### Code blocks

- One command per code block
- Explanatory text goes outside the block as regular markdown
- Never put `#` comments inside code blocks

#### Before/After

For behavioral or UX changes, show both states in separate labeled code blocks.

#### Negative assertions in test plan

For removal or migration PRs, include "verify zero matches for X" items proving unwanted patterns are fully removed.

#### What NOT to include

- Test counts or passing numbers ("875 tests pass", "42 tests added")
- Git SHAs or commit hashes
- File-level line numbers
- Number of files or lines changed ("updated 12 files", "adds 340 lines")
- Details the reviewer can see in the diff
- Redundant context already visible in `git log`
- An invented issue link. Write `Fixes #N` only for an issue number the user, the branch name, or a commit supplied. (The merge commit title takes ` (#N)`; see the merge-commit skill.)
- **Within-branch tactical narrative** — renames of unshipped symbols, "no longer X" / "previously Y" phrasing, diff paraphrases, or `### Fixes` framing for behavior that never shipped. Belongs in the commit messages of the commits that did the work. Keep such text only when a user of the latest published release experienced the old name, behavior, or bug.

#### Whole-branch perspective

Describe the branch's **net shipped result**, not its internal evolution.
Ignore fixup commits, reverts-then-re-adds, and intermediate WIP states.

### 4. Present and Create

Output shape: the proposed title and full body, then one question. The
chat text around the body is plain prose with no bold labels, and never
asks for an issue number.

- Ask whether to:
  1. Create the PR via `gh pr create`
  2. Just output the description (user will create manually)
- Without an interactive question tool, take option 2: output the
  description and stop. A request that says to create the PR authorizes
  `gh pr create` and the push it needs, nothing else.
- **If creating the PR:**
  - Check if the branch has been pushed; if not, push it with `git push -u origin <branch>`
  - Never push to `main` or `master`
  - Use heredoc for the body to preserve formatting:

    ```bash
    gh pr create --title "the title" --body "$(cat <<'EOF'
    ## Summary
    ...
    EOF
    )"
    ```

  - If the user provided `$ARGUMENTS` containing a hint about a linked issue, add `--body` content accordingly
  - When `gh` is missing or unauthenticated, stop: say the PR was not created and name the fix (`gh auth login`); the drafted description stays valid
- Return the PR URL when done

A run that stops early (empty log, no base, `gh` failure) is one
sentence saying what happened and that nothing changed, then what the
user must do.

---

## Rules

- **Never** force-push, run destructive git commands, or push to `main` or `master`.
- **Always** show the full description before creating the PR.
- **Language-agnostic**: discover test, lint, and typecheck commands from `AGENTS.md` / `CLAUDE.md`; never hardcode a tool's commands.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
