---
name: bump
description: "Use when discovering and confirming the next version from a project's own release scheme before cutting the release."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "[patch|minor|major|prerelease|final|<version>] [--push] [--tag] [--push-tag]"
user-invocable: true
disable-model-invocation: true
---

# Bump to the Next Version

Discover the project's current version and versioning scheme, work out
what "next" means, get the user's explicit choice, then run the full
`/release:cut` procedure at the chosen version.

Arguments: $ARGUMENTS

First, read `../../references/release-conventions.md`. The safety
contract in `../cut/SKILL.md` applies unchanged. This skill writes no
prose of its own; `cut` writes the changelog and commit message.

---

## Phase 1: Discover the Current Position

Gather three signals and check they agree:

1. **Manifest version** — from the version-bearing files (conventions
   reference).
2. **Latest tag** — `git tag --sort=-creatordate | head -20`, noting
   the prefix convention and the increment vocabulary the project has
   actually used (aN, bN, rcN, postN, devN, `-next.N`, plain semver).
3. **CHANGES unreleased header** — the version it already targets.
   A stable-track header like `## <project> 0.63.x (unreleased)`
   constrains the next release to the `0.63` series unless the user
   overrides; a prerelease-track header names the next version
   outright.

If the signals disagree (manifest ahead of tags, CHANGES targeting a
different series), surface the discrepancy before proposing anything.

## Phase 2: Enumerate Candidates

Classify the scheme per the conventions reference and build the
candidate list from it as concrete versions, not abstract bump names.
With current `0.1.9a1` on a prerelease track: next prerelease `0.1.9a2`
(the routine increment), graduate to final `0.1.9`, and segment
promotion (`a` → `b` → `rc`) only if the tag history uses those
segments. With current `0.1.9` on a stable track: patch `0.1.10`, minor
`0.2.0`, major `1.0.0`, or a new prerelease series (`0.2.0a0`, or
`0.2.0-next.0` on npm) in the project's own vocabulary.

Do not offer `post`/`dev` releases unless the user asks or the argument
names one.

## Phase 3: Resolve the Version

- **Explicit version argument** (e.g. `0.2.0a0`) — validate it sorts
  after the current version and fits the scheme, then proceed. If it
  breaks the scheme (a `-next.N` version in a PEP 440 project),
  stop and ask.
- **Bump-type argument** (`patch`, `minor`, `major`, `prerelease`,
  `final`) — map it to the concrete candidate. If the mapping is
  ambiguous for this scheme (`prerelease` on a stable track could
  mean `0.1.10a0` or `0.2.0a0`; `patch` on a prerelease track could
  mean the next prerelease or the graduated final), do not guess —
  present the interpretations via `AskUserQuestion`.
- **No argument** — present the Phase 2 candidates via
  `AskUserQuestion`. Recommend the increment the project performed
  most recently (its last two tags show the habitual step). Label
  each option with the concrete version and a one-line description of
  when it is the right choice.

Never proceed on an inferred version. The user picks; the panel
selection is the confirmation.

## Phase 4: Cut

Run the complete `/release:cut` procedure
(`../cut/SKILL.md`, Phase 1 onward) with the
chosen version, forwarding any `--push` / `--tag` / `--push-tag`
flags the user passed.

The CHANGES step opens the next unreleased header as the conventions
reference specifies.
