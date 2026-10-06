---
name: commit
description: >-
  Create a git commit following project conventions
disable-model-invocation: true
allowed-tools: ["Bash", "Read"]
metadata:
  argument-hint: "[optional hint about the changes, e.g. 'fix the auth bug']"
  source: "plugins/commit/skills/commit/SKILL.md"
---

# Git Commit

Create a git commit using the project's commit conventions.

User hint: $ARGUMENTS

## Commit Convention

Read the project's AGENTS.md and/or CLAUDE.md for the commit message format:

- Subject line format (`Scope(type[detail]) description`, Conventional Commits
  `type(scope): description`, or another pattern)
- Body structure (such as `why:/what:` sections)
- Component naming conventions

With no project convention, use Conventional Commits. Match the recent
commits' capitalization, tense, and level of detail.

Branch-internal narrative (renames, refactors, attempts-then-reverts,
intermediate states) belongs in the commit message, not in the code,
docstrings, README, or CHANGES the commit modifies.

---

## Procedure

### 1. Gather State

Run these and read the output:

- `git branch --show-current`: the current branch.
- `git status --short`: the working tree.
- `git diff --cached --stat` and `git diff --stat`: staged and unstaged changes.
- `git diff HEAD`: the full diff.
- `git log --oneline -10`: recent commits, for style matching.

A failure of the first command means this is not a git repository: report it
and stop. `git diff HEAD` fails in a repository with no commits; use
`git diff --cached` there. No changes: report "Nothing to commit" and stop.

### 2. Analyze Changes

- Review the full diff to understand what changed
- Determine the commit type (`feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`, etc.)
- Determine the scope/component from the files and modules touched
- Check topic coherence: if the changes span unrelated topics, warn the user and suggest splitting into separate commits

### 3. Determine Staging

- **If files are already staged** (`git diff --cached` is non-empty): respect the user's staging — only commit what is staged
- **If nothing is staged**: auto-stage changed files, but:
  - **Never stage sensitive files**: `.env`, `.env.*`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `*.p12`, `*.pfx`, `id_rsa*`, `*.keystore`
  - Use `git add <specific-files>` — never `git add -A` or `git add .`
  - Tell the user which files you are staging

### 4. Draft Commit Message

- Follow the project's commit format
- Write the message per `references/prose-rules.md`
- If the user provided `$ARGUMENTS`, use it as a hint for the description — but always enforce the project's format
- Include a body (`why:/what:` or equivalent) when:
  - Multiple files are changed
  - The change is non-trivial
  - The diff is not self-explanatory
- **Show the proposed commit message** to the user before executing

#### Line wrapping

Wrap commit message body lines at 72 characters.

Overflow exceptions: never break these tokens across lines; place them at the
end of a line or on their own line:

- URLs
- commit hashes
- stack traces
- file paths
- long identifiers (class names, function signatures)

Let such a line run long rather than wrapping mid-token.

### 5. Version and Dependency Bumps

For version bumps and dependency updates, use this format.

**Single package** — compact subject with body:
```
scope(tool) old_version -> new_version
```
Body: link the release tag and changelog:
```
- https://github.com/owner/repo/releases/tag/vX.Y.Z
- https://github.com/owner/repo/blob/vX.Y.Z/CHANGELOG.md
```

**Multiple packages** — list each in the body:
```
scope(chore) Bump tool1, tool2, tool3

- tool1 1.2.0 -> 1.3.0 (March 5, 2026)
  - https://github.com/owner/tool1/releases/tag/v1.3.0
  - https://github.com/owner/tool1/blob/v1.3.0/CHANGELOG.md
- tool2 0.9.1 -> 0.10.0 (February 28, 2026)
  - https://github.com/owner/tool2/releases/tag/v0.10.0
  - https://github.com/owner/tool2/blob/v0.10.0/CHANGELOG.md
```

URL guidelines:
- Use `/releases/tag/` for release pages
- Use `/blob/<tag>/CHANGELOG.md` for changelogs pinned to the release tag — not `/blob/main/` unless no tags exist
- Use arrow notation for version transitions: `v1.2.0 → v1.3.0` or `1.2.0 -> 1.3.0`

### 6. Commit

- For single-line messages:
  ```
  git commit -m "the message"
  ```
- For messages with a body, use heredoc to preserve formatting:
  ```
  git commit -m "$(cat <<'EOF'
  subject line

  why: ...
  what:
  - ...
  EOF
  )"
  ```
- **If a pre-commit hook fails**:
  - Read the hook output to understand the failure
  - Fix the issue (formatting, lint, etc.)
  - Re-stage the fixed files
  - Create a new commit; the failed commit does not exist, so there is nothing to amend

### 7. Confirm Result

- Run `git log --oneline -1` to show the created commit
- Run `git status` to show the remaining working tree state
- Report success to the user

---

## Commit Quality Guide

### Do

- Match detail to the change: a small fix gets a concise body; a large feature
  gets structured sub-sections.
- Put motivation in `why:` and specific technical changes in `what:`.
- Give before/after numbers for performance changes.
- Show broken vs fixed behavior inline for bug fixes when it helps.
- Name an issue the commit closes with `Fixes #N`; link anything else with
  `See also: <URL>`.
- List the files changed when several modules are touched.

### Don't

- Vague subjects: "update code", "fix bug", "misc changes".
- Type repeated in the description: "feat: add new feature".
- The branch's own PR number in a branch commit. Only the merge commit's
  subject carries ` (#N)`, and changelog entries cite it.
- Bodies longer than the change warrants, or no body when changes span multiple
  files or the diff is non-obvious.
- Counts of files, lines, or tests; they duplicate `git diff --stat` and go
  stale.

---

## Rules

- Never run `git push`, `git push --force`, `git reset --hard`, or any
  destructive git command.
- Never use `--amend`, `--no-verify`, or `--no-gpg-sign`.
- Never create empty commits.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
