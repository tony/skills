# Entry rules

## Contents

- Project conventions outrank these defaults
- Categorize commits
- Format
- Voice
- What to exclude
- Proportionality
- Good and bad framing
- Voice check and target line
- Notes

## Project conventions outrank these defaults

Read the repo root for `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.cursor/rules/*`, `.github/AGENTS.md`, or equivalents, and record any
prescribed release-notes format or voice, section names, and commit format. A
project convention beats every default below; the existing changelog file
beats the fallbacks.

## Categorize commits

Parse the type from each commit subject, adapting to the project's commit
convention.

- `feat`: What's new. New functionality.
- `fix`: Bug fixes.
- `docs`: Documentation.
- `test`: Tests.
- `refactor`: only if user-visible.
- `chore`, `deps`: Development, only if consumer-visible (a minimum version
  bump, a build change that alters installation). Skip CI, linter, editor,
  dev-tooling, and test-infrastructure changes.
- `style`: skip.

Group before writing:

- An xfail commit, a fix commit, and an xfail-removal commit become one bug fix
  entry. The fix commit's message is the primary source.
- A deps commit plus a changelog doc commit become one entry, under Breaking
  changes for a minimum version bump, otherwise Development.
- Sequential `feat` commits on one component become one entry.
- Skip merge commits, lock-only changes, and internal-only refactors.

## Format

The existing file is the source of truth for shape. Copy the most recent
populated release's shape and adapt only the content: heading text and
capitalization (`Bug fixes` vs `Bug Fixes`), heading level, bullet or prose
style, blank-line spacing.

Section order, in priority:

1. The project's prescribed order.
2. The order the most recent populated release uses, with its names. Do not
   rename `Features` to `What's new`, and do not promote `Development` above
   `Bug fixes` if the project does not.
3. With no precedent, and only for sections that have entries: Breaking
   changes, What's new, Bug fixes, Documentation, Tests, Development.

Simple change, one bullet:

```markdown
- Brief description of the change (#123)
```

A new package, flag, behavior, or notable change to existing surface gets a
`####` heading and 2-4 lines of product-level prose: usefulness, integration,
trade-offs. Match the project's convention if it has one (paragraph-only,
bullet-only, another heading level). The fallback shapes:

```markdown
#### New package: `<name>`

One-paragraph description of what the user can do with it, how it
integrates with what they already have, and any explicit trade-off
or limitation. Drop-in compatibility statements live here. (#123)

#### New flag: `--<flag>` for `<command>`

What the flag enables and the default behaviour without it. Note
any non-obvious interaction with existing flags. (#123)

#### `<package>`: <product-level change>

For changes to existing packages, lead the heading with the package
name, then the user-visible change. Body explains what the user
sees differently and why it matters downstream. (#123)
```

Avoid commit-prefix headings like `#### cli(sync): ...`; they describe the
commit. Detail beyond 4 lines or a bullet list means splitting into one entry
per shipped surface.

PR references: `(#512)` when the number is known, `(#???)` when it is unknown.
An authentication, network, service, or tool failure does not establish that
no PR exists. When a reply includes PR status, use `unverified` for an
unsuccessful lookup unless the result explicitly establishes no matching PR;
only then use `none`.

## Voice

Product-facing, upgrade-decision oriented. The first sentence of each entry
answers one reader question: should I upgrade, will my code break, can I drop a
workaround or take a new affordance, was my bug fixed? Lead with what the user
gains, can do, or must know, never with what was implemented. Depth lives in
autodoc, source, and the linked PR.

- Mention a non-obvious integration story: drop-in compatibility, default
  activation, auto-derived settings, accepted-but-ignored keys with a warning.
- Present-tense titles: "Add support for...", not "Added support for...".
- Close every entry with the PR link.

## What to exclude

Rewrite a draft entry that contains any of these:

- Type signatures: `float | None`, `Optional[X]`, generics, return types.
- Signal, syscall, or kernel names: `SIGTERM`, `epoll`, `mmap`, "non-blocking fd".
- Internal mechanics: selectors, busy-loops, race windows, buffer sizes, lock
  files, the cause of a fix rather than its effect on the user.
- Dunder or private names: `__str__`, `_internal_helper`.
- Implementation flags, constants, and internal env vars.
- Numeric tallies: file, line, test, or commit counts.
- Git refs: SHAs, branch names, tag names, line numbers.
- Version predictions, per `branch-scope.md`.
- Non-user-visible work: behavior-neutral refactors, type-only annotations,
  internal renames, lint cleanups, CI tweaks, test infrastructure,
  dev-tooling bumps.
- Phantom fixes: a Fixes entry, or "no longer raises" phrasing, without
  evidence that a published release had the bug. `git tag --contains
  <introducing-commit>` finds local candidates; missing tags or shallow
  history do not prove that nothing shipped. Verify the release's source or
  published artifact before making the claim. A branch-only fix belongs in
  its feature's paragraph. When the introducing change is on the base and
  release status is unknown, omit the fix and note the missing evidence.
- The section heading repeated in the entry text.

## Proportionality

A simple bullet is 1-2 lines and a `####` entry 2-4; longer means splitting
by shipped surface. A sentence that reads like a docstring or stack trace goes
to the PR or autodoc. When the existing file sets its own proportionality,
match it.

## Good and bad framing

Bad describes the commit or leaks implementation; good describes what the user
sees.

- Bad: `cli(sync): Add structured error reporting to handler`
- Good: ``#### `cli sync`: Errored items now appear in the summary``, with the
  body "The summary block previously showed only successful and failed counts;
  errored items were silently dropped. Each errored item is now listed with its
  failure reason. (#512)"
- Bad: ``#### New `timeout=` keyword`` with a body naming `float | None`,
  `SIGTERM`, `SIGKILL`, and the exception's `__str__`.
- Good: ``#### New `timeout=` keyword``, body "``Foo.run()`` and ``Bar.run()``
  now accept a ``timeout``, with improved cleanup of stuck subprocesses when the
  deadline fires. (#42)"
- Bad: a paragraph on which internal command a lookup used to call.
- Good: `#### Improve handling of large datasets`, body "Lookups against datasets
  with thousands of entries no longer appear to hang. (#43)"
- `feat: Add 12 new test cases for parser`: skip. Internal coverage.

## Voice check and target line

Presentation to the user includes both, every run: one voice-check bullet per
entry, then one `Target` line.

Voice check: name each entry and the reader question its first sentence
answers.

```text
Voice check:
- Add `Cache.evict()` to drop a cached key: can I take a new affordance?
- `cli sync`: errored items now appear in the summary: was my bug fixed?

Target: CHANGES.md, Unreleased, Features, after the "### Features" heading. No version assigned, no release cut.
```

An entry that answers none of the four is a commit summary. Rewrite it before
presenting; never present it with a blank.

A `Target` that names anything but the unreleased section means the user
explicitly asked for a release. Otherwise stop and re-read the branch-scope
rules.

## Notes

A reply is its template and nothing else: the result sentence, the summary
line, entries, voice check, `Target`, then `Notes`. Prose outside the
template is cut. `Notes` holds only these bullets, each stated once:

- A change left out, with the evidence that is missing.
- An unverified PR number: `(#???)` appears and the lookup failed or was not
  authenticated.
- Work left undone that needs the user's approval, named, with no offer to do
  it and no advice on how to proceed.
- A retained mixed commit: its subject and that it also changes code, nothing
  about its changelog lines.
- The backup branch and the push command, for a rewrite.

Everything else is cut: advice ("you may want"), citations of rules, checks
that passed, critique or description of old entries, and the reason a heading
was not created.
