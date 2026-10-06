---
name: merge-commit
description: "Use when drafting a merge or squash-merge commit message for the current branch, to copy into the merge workflow."
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
argument-hint: "[optional hint, e.g. 'version bump' or 'breaking change']"
user-invocable: true
disable-model-invocation: true
---

# Generate Merge Commit Message

Draft a merge commit message for the current branch. It is the
**user-facing, product-level** summary that appears in `git log --merges`
on the main branch. Write it per `../../references/prose-rules.md`.

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

An empty log means nothing is ahead of the base; say so and stop.

### 2. Analyze changes

- Review the full diff and **all** commits, not only the latest.
- Classify the change: feature, fix, refactor, version bump, CI, docs,
  breaking change, runtime version drop. Assess its scope.
- Note any PR number visible in the branch name or commits.
- Describe the **net shipped result**: collapse fixups,
  reverts-then-re-adds, and WIP states. Keep rename history, `### Fixes`
  for behavior that never shipped, and "no longer X" framing out unless a
  user of the latest published release experienced the old name,
  behavior, or bug.

### 3. Read project conventions

Read `AGENTS.md` and `CLAUDE.md` for merge commit conventions. When the
project uses a scope format such as `scope(type[detail])`, match it in
the title.

### 4. Draft the message

#### Title line

- Under 70 characters.
- Ends with ` (#N)` when the PR number is known. The suffix belongs to
  the merge commit title only; commits on the branch never carry `#N`.
- Matches the project's scope format when one exists.
- Describes the **impact**, what changed for the user, not the
  implementation.

#### Body, proportional to the change

- **Small change** (1-3 file fix, simple bump): title only.
- **Medium change** (feature, targeted refactor, fix with a root cause):
  an opening paragraph of 2-4 sentences on what changed and why, then
  bullets with **bold labels** for specific changes.
- **Large change** (multi-module feature, major refactor, migration): a
  structured body from the patterns below.

End the message with no `Co-Authored-By`, "Generated with", or other
tool trailer, and use no emoji.

Wrap body lines at 72 characters. Never break a URL, hash, path, stack
trace, or long identifier mid-token; let that line run long.

#### Body patterns, use only what applies

**Features, refactors, bug fixes:**
- Opening paragraph: what and why.
- Bullets with **bold labels** for specific changes.
- `Breaking changes:` with migration guidance, when applicable.
- Cross-references: `Fixes #N`, `See also:`, companion PR links.
- Version compatibility notes (environment tables, test matrices).

**Bug fixes with a non-obvious root cause:**
- A root-cause paragraph, numbered reproduction steps if they help,
  and environment or version tables when the bug is version-specific.

**API refactors with migration paths:**
- Old/new tables for renamed methods, parameters, or modules.
- Deprecation notices with a timeline, and `Breaking changes:`.

**Version bumps:**
- Arrow notation: `v1.2.3 -> v1.3.0` or `v1.2.3 → v1.3.0`.
- A release tag URL and changelog URL per package, and the release date
  when known.
- Per-file scope notes when files change different dependencies.

**Runtime version drops:**
- The EOL date and links to the PEP and devguide references.

**Build and infra migrations:**
- Before/after tooling and why the migration was needed.

**Multi-module sync results:**
- Companion PR links, design decisions and trade-offs, and a qualitative
  test coverage summary.

#### What not to include

- Test counts or passing numbers ("875 tests pass")
- Git SHAs or commit hashes
- File-level line numbers
- The number of files changed
- Details the reviewer can see in the diff
- Context already visible in `git log`

### 5. Present the message

- Show the complete message in one fenced code block.
- Do not run any git write command; the user pastes the message into
  their merge workflow (GitHub merge button, `git merge --edit`, the
  squash-and-merge dialog).
- When the PR number is unknown, note where ` (#N)` goes.
- A run that stops early (empty log, no base) is one sentence saying
  what happened, then what the user must do.

## Rules

- **Never** run `git merge`, `git commit`, or any write operation; output only.
- **Never** force-push or run destructive git commands.
- **Language-agnostic**: discover conventions from `AGENTS.md` / `CLAUDE.md`; never hardcode a tool's commands.
