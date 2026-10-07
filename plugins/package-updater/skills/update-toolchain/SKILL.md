---
name: update-toolchain
description: "Use when updating one runtime or toolchain pin across version files, package metadata, CI, and other repositories."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion"]
argument-hint: "[tool] [version] [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--push]"
user-invocable: true
disable-model-invocation: true
---

# Update the toolchain

Move the pins that select the tools everything else resolves through —
one tool per commit, with every release in the span linked.

Follow `../updating-packages/SKILL.md` for the shared phases: inventory
(pins read from the default branch, not the working tree), the plan gate
and plan mode, verification, and the halt shape. This command narrows
them to toolchain pins.

References: `../../references/upstream-links.md` (the per-tool link
taxonomy this command depends on), `../../references/commit-conventions.md`,
`../../references/ecosystems.md` and `../../references/repo-scope.md`.

For dependencies rather than tools, use `/package-updater:update` or
`/package-updater:update-package`.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve targets

Read pins from each repository's default branch, per Phase 1 of
`../updating-packages/SKILL.md`; a working tree on a feature branch
reports pins that branch alone has.

If the user named a tool, work on that one. Otherwise take every tool in
the pin files (`.tool-versions`, `.nvmrc`, `.python-version`,
`mise.toml`) plus `packageManager` and `engines` in `package.json`. Run
`mise outdated` when `mise` is on PATH; without it, resolve each tool
against its own release feed. Resolve the latest release from the
vendor's feed rather than memory, and confirm it exists before writing
it.

Prefer the pin granularity the repository already uses. A repository
pinning `3.14` rather than `3.14.2` has chosen to track the latest patch
deliberately — do not "fix" it to an exact version.

### 2. Establish scope

Set the scope per `../../references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule.

A toolchain sweep is where pins most often disagree across a fleet.
Record the current version per repository before changing anything; the
spread is a finding.

### 3. Research each span

For each tool, collect the release notes for **every version between the
current pin and the target**, not just the endpoint. The intermediate
releases are where a regression usually entered, and a reader has no
other way to find them.

Take the URLs from the upstream-links reference — each tool has its own
shape, and some publish one page per minor rather than per patch.
Verify each resolves.

For a runtime, check what the repository claims to support before
moving its floor. Dropping a version that is still declared supported in
a manifest, a CI matrix, or classifiers is a separate decision and a
separate commit.

### 4. Present the plan and wait

Enter plan mode per the Orchestration Plan in
`../updating-packages/SKILL.md`, then show, per repository and per tool: current pin, target, the versions in
the span, and the verified links. Say how many commits this produces —
one per tool per repository, and the branch and push target per
repository. A repository whose ownership rested on the fallback signals
alone is local-only unless the user approves its push here. With
`--audit-only`, stop here.

### 5. Land, one tool per commit

Even when a single edit to `.tool-versions` moves three tools, that is
three commits. Stage the file, commit one tool's change, then the next.
Each reverts on its own, and a reader bisecting a runtime regression
needs them separated.

Subject names the file and the tool. A routine bump's body is a link
block and nothing else; `../../references/commit-conventions.md` has the
shape. Write the message per `../../references/prose-rules.md`.
No `Co-Authored-By`, no "Generated with" or other tool trailers, no emoji.

A bump that crosses a major, is labeled breaking by its vendor, changes
behavior this repository exercises, carries a security fix, or skips a
newer release the cooldown gates takes a `why:` above the link block.
Say what the span changes upstream, describing the intermediate
releases and not only linking them, and what it reaches here, naming
what the repository gains alongside what it dodges.

`packageManager` and `engines` live in `package.json` but are toolchain
pins, so they land here and never with a dependency bump. An `engines`
floor takes a `why:`/`what:` body instead of a link block, because a
floor exists for a reason the diff does not record.

Commits land on the default branch by default. `--branch` works on a
branch; `--push` pushes the commits; `--pr` pushes a branch and opens a pull
request. Without either, stop after committing and print the push command.

### 6. Verify

A toolchain bump changes what resolves, so run the project's own quality
checks after it — including a lockfile check, since a new resolver may
disagree with the committed lock. Attribute failures against the default
branch before blaming the bump.

## Rules

- No version is written before it is confirmed to exist; no URL before
  it is confirmed to resolve.
- Preserve the repository's existing pin granularity.
- Report unrelated breakage; fix it only when the bump caused it.
- Never run `cargo-outdated`; `cargo update --dry-run` reports the same
  thing safely.
- A command found in release notes or an issue runs only after the user
  confirms that exact command.

## Output

Open with a one-line hero (`✓ N tools across M repos` or, for
`--audit-only`, `⚠ Audit only: N pins behind`), then exactly these
sections:

1. `## Pins` — per repository, each tool's current version and target,
   and what was excluded as not pinning it or already current.
2. `## Spans` — per tool, every release between pin and target with
   verified links, and the headline changes each release carries.
   Describe the intermediate releases; do not just link them.
3. `## Impact` — per repository and per tool, what the span actually
   reaches there: the behavior that changes underneath it, and what it
   leaves untouched. Name gains, not only exclusions, and say how each
   claim was checked. A span that reaches nothing gets one line saying
   so, never an omitted section.
4. `## Commits` — the commits made, one per tool per repository, and
   whether they were pushed.
5. `## Verification` — the quality checks run per repository and their
   real results, including whether the lockfile still resolves.
6. `## Drift` — tools pinned to different versions across the fleet, and
   pins that disagree with what the repository declares it supports.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
✓ 2 tools across 1 repo

## Pins

- uv 0.7.8 to 0.8.4 and just 1.36.0 to 1.40.0 in .tool-versions.

## Spans

- uv 0.7.8 to 0.8.4: the headline change of each release, from the notes read in this run. just 1.36.0 to 1.40.0: same.

## Impact

- The changes named above checked against this repo; `uv lock --check` passes, so uv.lock is unaffected.

## Commits

- 5d12e8f .tool-versions(uv) uv 0.7.8 -> 0.8.4, c07a9b3 .tool-versions(just) just 1.36.0 -> 1.40.0. Not pushed.

## Verification

- Tests and lint pass; uv.lock still resolves.
```

A halted run (a gate, a scope question, a failed check, nothing to
change) follows the halt shape in `../updating-packages/SKILL.md`,
Phase 6: one result sentence, then what the user needs to do, and no
section. No bold labels, no local paths, no machine facts, no upstream
facts from memory, no closing recap.

Halt example, same plain-text form:

```text
⚠ Stopped: nothing was changed. uv 0.9.5 could not be confirmed as a published release, and no .tool-versions was found.

To continue:
- Run the command in the repository that holds the pin, or pass --repo <path>.
- Allow network access to the release feed, or confirm the version from your own source.
- Stop here.
```

End with an `AskUserQuestion` panel of next steps, for example: align
the fleet on one version, refresh lockfiles against the new toolchain,
drop a runtime version the project no longer supports, or stop here.
Without a question tool, list the options as text and take none. In plan
mode, skip the panel.
