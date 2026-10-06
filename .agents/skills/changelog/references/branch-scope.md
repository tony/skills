# Branch scope

## Contents

- A branch is not a release
- The one exception
- Base branch
- Changelog file
- Whole-branch perspective

## A branch is not a release

Changelog skills document changes; they do not ship them. Every run is
release-agnostic unless the user explicitly asks for a release (see below),
whatever the branch is named and however release-shaped the commits look.

- Never create, rename, or date a version heading (`## v1.53.0`,
  `## [1.2.3] - YYYY-MM-DD`). Entries land in the unreleased section.
- Never state or predict the version the changes will land in: not in entry
  text, headings, the commit message, or the summary shown to the user. Other
  work may land first, and the maintainer decides when to cut.
- Never derive a version from the commits. A breaking change does not make
  this `2.0.0`, and a `feat` does not make it a minor bump. Do not reason
  about SemVer.
- Never edit version files (`pyproject.toml`, `package.json`, `Cargo.toml`,
  `__about__.py`, `version.*`), create tags, or convert an `Unreleased` or
  placeholder heading into a version heading.

If the changelog has no unreleased section, ask the user what to call it,
mirroring the project's convention, and create that. Never create a version
heading.

## The one exception

Cut or prepare a release only when the user explicitly asks and the version is
settled: "cut v1.53.0", "prepare the 2.0 release", "this is the release branch
for 0.9.4, date the heading".

None of these is an explicit request:

- A branch named `release/1.2`, `rc-3`, or `v2`.
- A milestone, label, or PR title mentioning a version.
- A version bump already in the branch's diff.
- A commit message that references an upcoming release.

An ambiguous ask ("update the changelog for the release") gets a question:
which version, and is a release cut intended. Until answered, stay in the
unreleased section.

## Base branch

The base is the PR's `baseRefName` when the branch has a PR, so stacked
branches diff against their parent:

```console
$ gh pr view --json baseRefName
```

Without a PR, take trunk from `git symbolic-ref refs/remotes/origin/HEAD`
(strip `refs/remotes/origin/`). If that fails, use `main`, then `master`,
whichever exists. Compare against `origin/<base>`. When the current branch is
the base, report "Already on the base branch, nothing to generate" and stop.

## Changelog file

Scan the repo root for `CHANGES`, `CHANGES.md`, `CHANGELOG`, `CHANGELOG.md`,
`HISTORY`, `HISTORY.md`, `NEWS`, `NEWS.md`. With several, take the one with the
most content. With none, ask the user which filename to create.

## Whole-branch perspective

Entries describe the net shipped result against the base, not the branch's
commit history. Collapse fixups, reverts-then-re-adds, and intermediate states;
an add-failing-test, fix, clean-up sequence becomes one bug fix entry.
