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

---

## Procedure

### 1. Gather State

Run the sensitive-path scan first. `references/sensitive.py` resolves
from this skill's directory to an absolute path; write that path literally
in the command:

```console
$ python3 /absolute/path/to/scripts/sensitive.py scan
```

It prints one line per changed path: `ok` or `refuse`, the state (`staged`,
`partial` for staged plus unstaged edits, `unstaged`, `untracked`), the path,
and the reason (a sensitive name, or a private-key or token marker in the
changed lines). It never prints a matched value. Exit 1 means a staged or
partial path is refused. When the user names one path in the request or hint
(for example "commit .env.test"), add `--allow <path>` for that path alone;
without that, a `refuse` path is never committed.

Run these and read the output:

- `git branch --show-current`: the current branch. Empty output means a
  detached HEAD.
- `git status --short`: the working tree.
- `git diff --cached --stat` and `git diff --stat`: staged and unstaged changes.
- `git diff HEAD --shortstat`: size of the tracked diff. Read the full diff
  when it is a few thousand lines or fewer; otherwise read it per file. Append
  `-- . ':(exclude)<path>'` for every `refuse` path (for example
  `git diff HEAD -- . ':(exclude).env'`), so a sensitive body never enters
  context. Never read a `refuse` file's content; name the file, not the
  value.
- `git ls-files --others --exclude-standard`: untracked files, which the diff
  omits. Read each new `ok` file; skim a large or binary file by name only.
- `git log --oneline -10`: recent commits, for style matching.
- `git symbolic-ref --short refs/remotes/origin/HEAD`: the remote's default
  branch. A failure means the default branch is unknown; compare against
  `main` and `master`.

A failure of the first command means this is not a git repository: report it
and stop. On a detached HEAD, commit nothing: say so and tell the user to
switch to a branch. Unmerged paths (`U` in the status) or a merge, rebase,
cherry-pick, or revert in progress (`git status` says so): commit nothing
and tell the user to finish or abort it. `git diff HEAD` fails in a repository with no commits; use
`git diff --cached` there. No tracked changes and no untracked files: report
"Nothing to commit" and stop.
On the default branch, commit anyway; the first reply line names the
branch (step 7) and nothing else says so. If the project's AGENTS.md or
CLAUDE.md requires feature branches, commit nothing and tell the user to
switch branches.

### 2. Analyze Changes

- Determine the commit type (`feat`, `fix`, `refactor`, `docs`, `chore`,
  `test`, `style`, etc.)
- Determine the scope/component from the files and modules touched
- Check topic coherence: if the changes span unrelated topics and nothing is
  staged, commit only the largest coherent topic's files, name the files left
  out. Staged files are always
  committed as staged. Do not wait for a reply.

### 3. Determine Staging

- **Files already staged** (`git diff --cached` is non-empty): respect the
  user's staging and commit only what is staged. If the scan refuses a
  staged or partial path, commit nothing: name the path and give the unstage
  command (`git restore --staged <path>`).
  Otherwise name the unstaged and untracked files left out. Before
  committing, note each `partial` path from the scan: it is partially staged.
- **Nothing staged**: stage changed `ok` files, never a `refuse` one. Name
  each skipped file in the reply and say it matches the sensitive-file list.
  Use `git add <specific-files>`, never `git add -A` or `git add .`, and name
  the staged files in the reply.

Once staging is final, read `git diff --cached --name-only`; step 7 compares
the commit against it.

### 4. Draft Commit Message

- Follow the project's commit format
- Write the message per `references/prose-rules.md`
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

```console
$ git commit -m "$(cat <<'COMMIT_MSG_END'
subject line

why: ...
what:
- ...
COMMIT_MSG_END
)"
```

If a pre-commit hook fails, note the rejection (what it rejected) for the
step 7 bullet:

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

Read the result back; the reply states what these commands show, not what
was intended:

- `git show --stat --format='%h%n%B' HEAD`: the short hash, the message as
  stored (a hook can rewrite it), and the committed paths.
- `git branch --remotes --contains HEAD`: empty output means no
  remote-tracking ref holds the commit.
- `git status --short`: the remaining working tree.

Compare the committed paths with the index read in step 3. A difference
(a hook added or dropped a path), or a committed path that status now shows
modified (a hook rewrote it after staging), gets its own bullet naming the
paths.

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

The reply is impersonal: no first person ("I committed", "tell me").
The first line is the hash, the stored subject, and `(local, not pushed)`
when the remote-tracking check was empty; on a default branch it reads
`(local on <branch>, not pushed)` with the branch's name. When a
remote-tracking ref holds the commit, write `(on <ref>)` instead. The stored
body follows verbatim when there is one. Bullets cover only: files staged,
files left out, the working tree state, a hook that changed the committed paths or message, and, whenever a hook
rejected any attempt in step 6, one bullet saying what it rejected and what
changed before the commit (required in that case). Skip the working-tree
bullet when the left-out bullets already name every remaining file, unless
it adds a fact. Add no other advice or remarks, including why a commit
landed on the default branch.

A stopped run is one result sentence, then what the user needs to do (for a
refused path, the command `git restore --staged <path>`). Add nothing else:
no `.gitignore` tips, secret-handling guidance, how to override the scan,
how to remove a secret from a file, or follow-up suggestions.

```text
Nothing committed: a merge is in progress and lib/parse.py has unresolved conflicts.
Resolve them, run `git add lib/parse.py`, then `git commit`; or run `git merge --abort`.
```

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


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
