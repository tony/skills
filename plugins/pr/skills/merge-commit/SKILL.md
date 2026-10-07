---
name: merge-commit
description: "Use when drafting a merge or squash-merge commit message for the current branch, to copy into the merge workflow."
allowed-tools: ["Bash", "Read"]
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

Follow `../../references/branch-context.md` to find the base and gather the branch's change.

### 2. Analyze changes

- Review the full diff and **all** commits, not only the latest.
- Classify the change: feature, fix, refactor, version bump, CI, docs,
  breaking change, runtime version drop.
- Note any PR number visible in the branch name or the user's hint.
- Describe the **net shipped result**: collapse fixups,
  reverts-then-re-adds, and WIP states. Leave out rename history,
  `### Fixes` for behavior that never shipped, and "no longer X" framing
  unless a user of the latest published release experienced the old
  name, behavior, or bug.

### 3. Read project conventions

Read `AGENTS.md` and `CLAUDE.md` for merge commit conventions. When the
project uses a scope format such as `scope(type[detail])`, match it in
the title.

### 4. Draft the message

#### Title line

- Under 70 characters.
- Ends with ` (#N)` when the PR number is known. The suffix belongs to
  the merge commit title only; commits on the branch never carry `#N`.
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

- **Features, refactors, bug fixes:** opening paragraph (what and why),
  bold-labeled bullets, `Breaking changes:` with migration guidance,
  cross-references (`Fixes #N`, `See also:`, companion PR links), and
  version compatibility notes.
- **Bug fixes with a non-obvious root cause:** a root-cause paragraph,
  numbered reproduction steps if they help, environment or version
  tables when the bug is version-specific.
- **API refactors with migration paths:** old/new tables for renamed
  methods, parameters, or modules; deprecation notices with a timeline.
- **Version bumps:** `v1.2.3 -> v1.3.0` notation, and per-file scope
  notes when files change different dependencies.
- **Runtime version drops:** the dropped version and why.

Use only URLs, versions, and dates present in the diff, lockfile, or
fetched this run; omit the rest.
- **Build and infra migrations:** before/after tooling and why.
- **Multi-module sync results:** companion PR links, design decisions
  and trade-offs, and a qualitative test coverage summary.

#### What not to include

- Test counts or passing numbers ("875 tests pass")
- Git SHAs, file-level line numbers, or the number of files changed
- Details the reviewer can see in the diff or `git log`

### 5. Present the message

Do not run any git write command; the user pastes the message into
their merge workflow (GitHub merge button, `git merge --edit`, the
squash-and-merge dialog). When the PR number is unknown, note where
` (#N)` goes. A run that stops early (empty log, no base) is one
sentence stating the stop and what the user must do, with no
colon-delimited aside.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`). The message is one
fenced block:

````text
Merge commit message for 3 commits on chore/bump-ruff:

```text
deps(chore[ruff]) Bump ruff to 0.9.2 (#58)

Picks up the fix for false positives in the import-sorting rule.

- Bump ruff from v0.8.6 -> v0.9.2 in the lint extra.
- Reformat two files the new release now flags.
```

The PR number was taken from the branch name; correct it if wrong.
````

## Rules

Never run `git merge`, `git commit`, or any write operation; output only.
Never force-push or run destructive git commands.
