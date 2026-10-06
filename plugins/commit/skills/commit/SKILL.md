---
name: commit
description: Create a git commit following project conventions
allowed-tools: ["Bash", "Read"]
argument-hint: "[optional hint about the changes, e.g. 'fix the auth bug']"
user-invocable: true
disable-model-invocation: true
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

---

## Procedure

### 1. Gather State

Run these and read the output:

- `git branch --show-current`: the current branch.
- `git status --short`: the working tree.
- `git diff --cached --stat` and `git diff --stat`: staged and unstaged changes.
- `git diff HEAD`: the full diff of tracked files.
- `git ls-files --others --exclude-standard`: untracked files, which the diff
  omits. Read each new file that is not sensitive (see Step 3).
- `git log --oneline -10`: recent commits, for style matching.

A failure of the first command means this is not a git repository: report it
and stop. `git diff HEAD` fails in a repository with no commits; use
`git diff --cached` there. No tracked changes and no untracked files: report "Nothing to commit" and stop.
On `main`, `master`, or the remote's default branch, say so in the proposal in
Step 4 and commit anyway; the commit stays local.

### 2. Analyze Changes

- Review the full diff to understand what changed
- Determine the commit type (`feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`, etc.)
- Determine the scope/component from the files and modules touched
- Check topic coherence: if the changes span unrelated topics, warn the user and suggest splitting into separate commits

### 3. Determine Staging

- **If files are already staged** (`git diff --cached` is non-empty): respect the user's staging and commit only what is staged. Name the unstaged and untracked files left out.
- **If nothing is staged**: auto-stage changed files, but:
  - **Never stage sensitive files**: `.env`, `.env.*`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `*.p12`, `*.pfx`, `id_rsa*`, `*.keystore`. Name each skipped file and why in the reply.
  - Use `git add <specific-files>` — never `git add -A` or `git add .`
  - Tell the user which files you are staging

### 4. Draft Commit Message

- Follow the project's commit format
- Write the message per `../../references/prose-rules.md`
- No `Co-Authored-By` or other trailers naming a tool, no "Generated with"
  footer, no emoji. Hosts add these by default; leave them out.
- If the user provided `$ARGUMENTS`, use it as a hint for the description — but always enforce the project's format
- Include a body (`why:/what:` or equivalent) when:
  - Multiple files are changed
  - The change is non-trivial
  - The diff is not self-explanatory
- **Show the proposed commit message**, then commit without waiting for a reply.

#### Line wrapping

Wrap body lines at 72 characters. Never break a URL, commit hash, stack
trace, file path, or long identifier across lines; let that line run long.

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

Confirm each tag and its date exist (`gh release view <tag> --repo owner/repo`,
or `git ls-remote --tags <url> <tag>`) before writing the URLs. Omit a date or
URL that cannot be confirmed.

Pin changelog links to the release tag, not `/blob/main/`, unless no tags
exist.

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
  - After two failed attempts, stop and report the hook output

### 7. Confirm Result

- Run `git log --oneline -1` to show the created commit
- Run `git status` to show the remaining working tree state

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Staged:** ...`):

```text
42881ff auth(fix[token]) Reject expired tokens (local, not pushed)

- Staged src/auth.py and tests/test_auth.py.
- Left .env unstaged: it holds credentials.
- Working tree is clean.
```

A stopped run is one result sentence, then what the user needs to do.

---

## Commit Quality Guide

### Do

- Match detail to the change: a small fix gets a concise body.
- Give before/after numbers for performance changes.
- Show broken vs fixed behavior inline for bug fixes when it helps.
- Name an issue the commit closes with `Fixes #N`; link anything else with
  `See also: <URL>`.

### Don't

- Vague subjects: "update code", "fix bug", "misc changes".
- The branch's own PR number in a branch commit. Only the merge commit's
  subject carries ` (#N)`, and changelog entries cite it.
- Counts of files, lines, or tests; they duplicate `git diff --stat` and go
  stale.

---

## Rules

- Never run `git push`, `git push --force`, `git reset --hard`, or any
  destructive git command.
- Never use `--amend`, `--no-verify`, or `--no-gpg-sign`.
- Never create empty commits.
