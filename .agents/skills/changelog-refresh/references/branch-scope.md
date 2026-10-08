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
whatever the branch is named.

- Never create, rename, or date a version heading (`## v1.53.0`,
  `## [1.2.3] - YYYY-MM-DD`). Entries land in the unreleased section.
- Never state, predict, or derive the version the changes will land in, in
  any text you write (entries, headings, commit message, summary). A breaking
  change does not make this `2.0.0`; do not reason about SemVer.
- Never edit version files (`pyproject.toml`, `package.json`, `Cargo.toml`,
  `__about__.py`, `version.*`), create tags, or convert an `Unreleased` or
  placeholder heading into a version heading.

If the changelog has no unreleased section, ask the user what to call it,
mirroring the project's convention, and create that. Never create a version
heading. Without a question tool, propose `## Unreleased` (or the project's
spelling) in the presented entries and flag it as a guess.

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
unreleased section. Without a question tool, print the question, stay in the
unreleased section, and cut nothing.

## Base branch

The base is the PR's `baseRefName` when the branch has a PR, so stacked
branches diff against their parent:

```console
$ gh pr view --json baseRefName
```

Without a PR, take trunk from `git symbolic-ref refs/remotes/origin/HEAD`
(strip `refs/remotes/origin/`). If that fails, use `main`, then `master`,
whichever exists. Run `git fetch origin <base>` before comparing against
`origin/<base>`; if the fetch fails, say the comparison may be stale. With no
`origin` remote, compare against the local `<base>` branch wherever a skill
says `origin/<base>`, and say so. When the current branch is the base, report
"Already on the base branch, nothing to generate" and stop.

## Changelog file

Scan the repo root for `CHANGES`, `CHANGES.md`, `CHANGELOG`, `CHANGELOG.md`,
`HISTORY`, `HISTORY.md`, `NEWS`, `NEWS.md`. With several, take the one with the
most content. With none, ask the user which filename to create, then create it with Bash; without a
question tool, propose `CHANGES.md` as a guess and create nothing before approval.

## Whole-branch perspective

Entries describe the net shipped result against the base, not the branch's
commit history. Collapse fixups, reverts-then-re-adds, and intermediate states;
an add-failing-test, fix, clean-up sequence becomes one bug fix entry.
