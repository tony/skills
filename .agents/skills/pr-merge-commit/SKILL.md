---
name: pr-merge-commit
description: >-
  Use when drafting a merge or squash-merge commit message for the current
  branch, to copy into the merge workflow.
disable-model-invocation: true
allowed-tools: ["Bash", "Read"]
metadata:
  argument-hint: "[optional hint, e.g. 'version bump' or 'breaking change']"
  source: "plugins/pr/skills/merge-commit/SKILL.md"
---

# Generate Merge Commit Message

Draft a merge commit message for the current branch. It is the
user-facing, product-level summary that becomes the commit on the main
branch, whether the merge is a merge commit or a squash. Write it per
`references/prose-rules.md`.

User hint: $ARGUMENTS

## Procedure

### 1. Gather context

Follow `references/branch-context.md` to find the base and gather the branch's change.

### 2. Analyze changes

- Review the full diff and all commits, not only the latest.
- Classify the change: feature, fix, refactor, version bump, CI, docs,
  breaking change, runtime version drop.
- Note any PR number visible in the branch name or the user's hint.
- Describe the net shipped result: collapse fixups,
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

- Under 70 characters, counting the ` (#N)` suffix.
- Ends with ` (#N)` when the PR number is known (a number in the hint,
  the branch name, or the branch's PR). The suffix belongs to the merge
  commit title only; commits on the branch never carry `#N`. When the
  number is unknown, leave the suffix off and tell the user to append it.
- Describes the impact, what changed for the user, not the
  implementation.

#### Body, proportional to the change

- Small change (1-3 file fix, simple bump): title only.
- Medium change (feature, targeted refactor, fix with a root cause):
  an opening paragraph of 2-4 sentences on what changed and why, then
  plain bullets for specific changes.
- Large change (multi-module feature, major refactor, migration): a
  structured body from the patterns below.

Add no `Co-Authored-By`, "Generated with", or other tool trailer, and no
emoji.

Wrap body lines at 72 characters. Never break a URL, hash, path, stack
trace, or long identifier mid-token; let that line run long.

#### Body patterns, use only what applies

- Features, refactors, bug fixes: opening paragraph (what and why),
  plain bullets, `Breaking changes:` with migration guidance,
  cross-references (`Fixes #N` only for an issue number the user, the branch name, or a commit supplied; `See also:`, companion PR links), and
  version compatibility notes.
- Bug fixes with a non-obvious root cause: a root-cause paragraph,
  numbered reproduction steps if they help, and the affected versions
  in a sentence when the bug is version-specific.
- API refactors with migration paths: old and new names as `old -> new` bullets for renamed
  methods, parameters, or modules; deprecation notices with a timeline.
- Version bumps: `v1.2.3 -> v1.3.0` notation, and per-file scope
  notes when files change different dependencies.
- Runtime version drops: the dropped version and why.
- Build and infra migrations: before/after tooling and why.
- Multi-module sync results: companion PR links, design decisions
  and trade-offs, and a qualitative test coverage summary.

Use only URLs, versions, and dates present in the diff, lockfile, or
fetched this run; omit the rest.

#### What not to include

- Test counts or passing numbers ("875 tests pass")
- Git SHAs, file-level line numbers, or the number of files changed
- Details the reviewer can see in the diff or `git log`

### 5. Present the message

Do not run any git write command; the user pastes the message into
their merge workflow (GitHub merge button, `git merge --edit`, the
squash-and-merge dialog).

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

````text
Merge commit message for 3 commits on chore/bump-ruff:

```text
deps(chore[ruff]) Bump ruff to 0.9.2 (#58)

Picks up the fix for false positives in the import-sorting rule.

- Bump ruff from v0.8.6 -> v0.9.2 in the lint extra.
- Reformat two files the new release now flags.
```

The PR number came from the branch name, and the base is the local origin/main, which may be stale.
````

After the message, add one line only for a fact the user must act on: where the PR number came from, the number to append when none was found, or a base other than `origin/<trunk>`. Always name the base and say it is the local `origin/<trunk>`, which may be stale, unless the user fetched it this session. Do not explain the message's wording or the commit history.

A run that stops early (empty log, no base) is one sentence stating the stop and that nothing changed, then what the user must do. No colon-delimited aside, no local paths. Reply in this shape:

```text
chore/bump-ruff has no commits ahead of origin/main, so no message was drafted and nothing changed. Commit your changes, then run this again.
```

## Rules

Never run `git merge`, `git commit`, or any write operation; output only.
Never force-push or run destructive git commands.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
