---
name: package-updater-update-toolchain
description: >-
  Use when updating one runtime or toolchain pin across version files,
  package metadata, CI, and other repositories.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "WebSearch", "WebFetch", "Task", "AskUserQuestion"]
metadata:
  argument-hint: "[tool] [version] [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--no-push]"
  source: "plugins/package-updater/skills/update-toolchain/SKILL.md"
---

# Update the toolchain

Move the pins that select the tools everything else resolves through —
one tool per commit, with every release in the span linked.

References, all under `../../references/`: `upstream-links.md` (the
per-tool link taxonomy this command depends on), `commit-conventions.md`,
`ecosystems.md` and `repo-scope.md`.

For dependencies rather than tools, use the `package-updater-update` skill or
the `package-updater-update-package` skill.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve targets

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

Set the scope per `references/repo-scope.md`, which owns the
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
shape, and Node, Go and pnpm publish per minor rather than per patch.
Verify each resolves.

For a runtime, check what the repository claims to support before
moving its floor. Dropping a version that is still declared supported in
a manifest, a CI matrix, or classifiers is a separate decision and a
separate commit.

### 4. Present the plan and wait

Show, per repository and per tool: current pin, target, the versions in
the span, and the verified links. Say how many commits this produces —
one per tool per repository. With `--audit-only`, stop here.

### 5. Land, one tool per commit

Even when a single edit to `.tool-versions` moves three tools, that is
three commits. Stage the file, commit one tool's change, then the next.
Each reverts on its own, and a reader bisecting a runtime regression
needs them separated.

Subject names the file and the tool. A routine bump's body is a link
block and nothing else; `references/commit-conventions.md` has the
shape. Write the message per `references/prose-rules.md`.

A bump that crosses a major, is labeled breaking by its vendor, changes
behavior this repository exercises, carries a security fix, or skips a
newer release the cooldown gates takes a `why:` above the link block.
Say what the span changes upstream — describing the intermediate
releases, not only linking them — and what it reaches here, naming what
the repository gains alongside what it dodges.

`packageManager` and `engines` live in `package.json` but are toolchain
pins, so they land here and never with a dependency bump. An `engines`
floor takes a `why:`/`what:` body instead of a link block, because a
floor exists for a reason the diff does not record.

Commits land on the default branch by default. `--branch` works on a
branch; `--pr` opens a pull request; `--no-push` stops after committing.

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

## Output

Open with a one-line hero (`✓ N tools across M repos` or
`⚠ Audit only: N pins behind`), then exactly these sections:

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

End with an `ask-user-choice` panel offering next steps — for example:
align the fleet on one version, refresh lockfiles against the new
toolchain, drop a runtime version the project no longer supports, or
stop here. Skip the panel only in plan mode.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
