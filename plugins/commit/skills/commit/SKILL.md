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

Sensitive files: `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`,
`*.jks`, `*.p8`, `*.keystore`, `id_*` (but not `*.pub`), `*credentials*`,
`*secret*`, `*.tfvars`, `.git-credentials`, `.npmrc`, `.pypirc`, `.netrc`,
`.pgpass`. A name ending in `.example` or
`.sample` is not sensitive. The user may override for one path by naming it
in the request or hint (for example "commit .env.test"); that path alone
may be staged or committed. Without that, a match is never committed.

Run these and read the output:

- `git branch --show-current`: the current branch. Empty output means a
  detached HEAD.
- `git status --short`: the working tree.
- `git diff --cached --stat` and `git diff --stat`: staged and unstaged changes.
- `git diff HEAD --shortstat`: size of the tracked diff. Read the full diff
  when it is a few thousand lines or fewer; otherwise read it per file. Append
  `-- . ':(exclude)<path>'` for every sensitive path in the status output
  (for example `git diff HEAD -- . ':(exclude).env'`), so a sensitive body
  never enters context. Never read a sensitive file's content.
- `git ls-files --others --exclude-standard`: untracked files, which the diff
  omits. Read each new file that is not sensitive; skim a large or binary
  file by name only.
- `git log --oneline -10`: recent commits, for style matching.
- `git symbolic-ref --short refs/remotes/origin/HEAD`: the remote's default
  branch. A failure means the default branch is unknown; compare against
  `main` and `master`.

A failure of the first command means this is not a git repository: report it
and stop. On a detached HEAD, commit nothing: say so and tell the user to
switch to a branch. `git diff HEAD` fails in a repository with no commits; use
`git diff --cached` there. No tracked changes and no untracked files: report
"Nothing to commit" and stop.
On the default branch, commit anyway and say so in the reply; the commit
stays local. If the project's AGENTS.md or CLAUDE.md requires feature
branches, commit nothing and tell the user to switch branches.

### 2. Analyze Changes

- Determine the commit type (`feat`, `fix`, `refactor`, `docs`, `chore`,
  `test`, `style`, etc.)
- Determine the scope/component from the files and modules touched
- Check topic coherence: if the changes span unrelated topics and nothing is
  staged, commit only the largest coherent topic's files, name the files left
  out, and suggest committing them separately. Staged files are always
  committed as staged. Do not wait for a reply.

### 3. Determine Staging

- **Files already staged** (`git diff --cached` is non-empty): respect the
  user's staging and commit only what is staged. If a staged path matches the
  sensitive list (and the user did not override it), commit nothing: name the
  path and tell the user to unstage it (`git restore --staged <path>`).
  Otherwise name the unstaged and untracked files left out. Before
  committing, note each staged path that also has unstaged changes (listed by
  both `git diff --cached --name-only` and `git diff --name-only`): it is
  partially staged.
- **Nothing staged**: stage changed files, never a sensitive one. Name each
  skipped file in the reply and say it matches the sensitive-file list. Use
  `git add <specific-files>`, never `git add -A` or `git add .`. Tell the
  user which files you are staging.

### 4. Draft Commit Message

- Follow the project's commit format
- Write the message per `../../references/prose-rules.md`
- No `Co-Authored-By` or other trailers naming a tool, no "Generated with"
  footer, no emoji. Hosts add these by default; leave them out, and do not
  mention the omission in the reply.
- If the user provided `$ARGUMENTS`, use it as a hint for the description,
  and still enforce the project's format.
- Include a body (`why:/what:` or equivalent) when:
  - Multiple files are changed
  - The change is non-trivial
  - The diff is not self-explanatory
- Commit without waiting for a reply; the message appears once, in the final
  reply.

#### Line wrapping

Wrap body lines at 72 characters. Never break a URL, commit hash, stack
trace, file path, or long identifier across lines; let that line run long.

### 5. Version and Dependency Bumps

For version bumps and dependency updates, write the subject in the project's
subject format and name the tool with `old_version -> new_version`. The body
templates below link GitHub releases; adapt the URLs for another host.

Single package: link the release tag and changelog in the body.

```text
- https://github.com/owner/repo/releases/tag/vX.Y.Z
- https://github.com/owner/repo/blob/vX.Y.Z/CHANGELOG.md
```

Multiple packages: the subject names the tools in the project's subject
format, and the body lists each one.

```text
- tool1 1.2.0 -> 1.3.0 (<release date>)
  - https://github.com/owner/tool1/releases/tag/v1.3.0
  - https://github.com/owner/tool1/blob/v1.3.0/CHANGELOG.md
- tool2 0.9.1 -> 0.10.0 (<release date>)
  - https://github.com/owner/tool2/releases/tag/v0.10.0
  - https://github.com/owner/tool2/blob/v0.10.0/CHANGELOG.md
```

Confirm each tag and its date exist (`gh release view <tag> --repo owner/repo`,
or `git ls-remote --tags <url> <tag>`) before writing the URLs. Omit a date or
URL that cannot be confirmed.

Pin changelog links to the release tag, not `/blob/main/`, unless no tags
exist.

### 6. Commit

Pass every message, one line or many, through a quoted heredoc so backticks
and `$(...)` stay literal. Pick a delimiter that appears nowhere in the
message; never use double quotes for the message.

```bash
git commit -m "$(cat <<'COMMIT_MSG_END'
subject line

why: ...
what:
- ...
COMMIT_MSG_END
)"
```

If a pre-commit hook fails:

- Read the hook output to understand the failure.
- Fix the issue (formatting, lint, etc.) in the staged files only; leave
  unstaged files as they are.
- Re-stage only the paths the hook or your fix changed, and never a path
  noted as partially staged: `git add <path>` would stage its unstaged hunks
  too. If such a path needs re-staging, stop, name it, and tell the user to
  re-stage it with `git add -p`.
- Create a new commit; the failed commit does not exist, so there is nothing
  to amend. Never delete, disable, or reconfigure the hook.
- After two failed attempts, stop and report the hook output.
- If signing fails (`commit.gpgsign`), stop and report; never pass
  `--no-gpg-sign`.

### 7. Confirm Result

- Run `git log --oneline -1` to show the created commit
- Run `git status` to show the remaining working tree state

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
42881ff auth(fix[token]) Reject expired tokens (local, not pushed)

why: A token expiring exactly now was still accepted.

what:
- Compare with <= in is_expired.

- Staged src/auth.py and tests/test_auth.py.
- Left .env unstaged: it matches the sensitive-file list.
- A pre-commit hook rejected the first attempt (trailing whitespace in
  src/auth.py); fixed it and committed again.
- Working tree is clean.
```

The first line is the hash, the subject, and `(local, not pushed)`; on a
default branch it reads `(local on <branch>, not pushed)` with the branch's
name. The commit body follows
verbatim when there is one. Bullets cover only files staged, files left out,
the working tree state, and a hook rejection that preceded the commit (say
what it rejected and what you changed; include that bullet only when a hook
rejected an attempt). Skip the working-tree bullet when the
left-out bullets already name every remaining file, unless it adds a fact.
Add no other advice or remarks.

A stopped run is one result sentence, then what the user needs to do. Add
no other advice, such as `.gitignore` tips or follow-up suggestions.

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
- Never use `git commit -a` or `--all`; commit exactly the index.
