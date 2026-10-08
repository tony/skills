---
name: package-updater-update-toolchain
description: >-
  Use when updating one runtime or toolchain pin across version files,
  package metadata, and other repositories.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "[tool [version]]... [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--push]"
  source: "plugins/package-updater/skills/update-toolchain/SKILL.md"
---

# Update the toolchain

Move the pins that select the tools everything else resolves through —
one tool per commit, with every release in the span linked.

Follow the `package-updater-updating-packages` skill for the shared phases: inventory
(pins read from the default branch, not the working tree), discovery in
a detached throwaway worktree when the checkout is parked on a feature branch or
behind its remote,
the cooldown check, the plan gate and plan mode, verification, and the
halt shape. This command narrows them to toolchain pins.

References: `references/upstream-links.md` (the per-tool link
taxonomy this command depends on), `references/commit-conventions.md`,
`references/ecosystems.md`, `references/repo-scope.md` and
`references/cooldown-exemption.md`.

For dependencies rather than tools, use the `package-updater-update` skill or
the `package-updater-update-package` skill.

User arguments: $ARGUMENTS

## Procedure

### 1. Establish scope

Set the scope per `references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule.

### 2. Resolve targets

Read pins from each repository's default branch, per Phase 1 of
the `package-updater-updating-packages` skill; a working tree on a feature branch
reports pins that branch alone has.

If the user named a tool, work on that one. Otherwise take every tool in
the pin files (`.tool-versions`, `.nvmrc`, `.python-version`,
`.ruby-version`, `mise.toml`, `.mise.toml`, `rust-toolchain.toml`, the `go` and
`toolchain` lines of `go.mod`) plus `packageManager` and `engines` in
`package.json`; `references/repo_facts.py` prints these per repository
(`pins`); resolve its path from this skill's directory to an absolute
path and write it literally in the command. Run
`mise outdated` when `mise` is on PATH; without it, resolve each tool
against its own release feed. Resolve the latest release from the
vendor's feed rather than memory: for a tool released on GitHub, the tag
`gh api repos/<owner>/<repo>/releases/latest --jq .tag_name` prints;
for Node.js, the newest entry on the repository's line in
`https://nodejs.org/dist/index.json`.
For a Go toolchain, the newest stable entry of
`https://go.dev/dl/?mode=json`; for CPython, the newest stable release on
python.org's release feed (`https://www.python.org/api/v2/downloads/release/`).
Confirm the version exists before writing it.

Prefer the pin granularity the repository already uses. A repository
pinning `3.14` rather than `3.14.2` has chosen to track the latest patch
deliberately — do not "fix" it to an exact version.

A toolchain sweep is where pins most often disagree across a fleet.
Record the current version per repository before changing anything; the
spread is a finding.

### 3. Check the cooldown

Read the repository's cooldown configuration per the "Supply-chain
cooldown" section of `references/ecosystems.md`; a toolchain pin
uses the window the repository sets for its packages, and a repository
with none has no gate. For each target, read its publication time with
the command in the "Release publication time" section of that
reference. A target younger than the window stops that tool, even when
the user named the version: read `references/stopped-run.md` and use its cooldown form
with its values swapped: one sentence holding the publication day and the
date it becomes visible, then the options. Add no paragraph about the pin,
the commit, the config file or the user's instruction. When the user asks
for an older release instead, find the newest one outside the window by
listing publication dates, newest first:
for a GitHub tool, the command below; for Node.js,
`jq -r '.[] | [.version, .date] | @tsv'` on the dist index.

```console
$ gh api repos/<owner>/<repo>/releases \
    --paginate \
    --jq '.[] | select(.prerelease | not) | [.tag_name, .published_at] | @tsv'
```

Take it only when the user agrees; a release skipped this way earns a
`why:` in the commit. Exempt a tool only per
`references/cooldown-exemption.md`.

### 4. Research each span

For each tool, collect the release notes for **every version between the
current pin and the target**, not just the endpoint. The intermediate
releases are where a regression usually entered, and a reader has no
other way to find them.

List the span from the full release history, never the first page: the
release-list command above with `--paginate` for a GitHub tool, the
`releases` keys of `https://pypi.org/pypi/<name>/json` for a PyPI tool,
and the `time` keys of `https://registry.npmjs.org/<name>` for an npm
tool; keep stable versions only (drop prereleases and npm's `created` and
`modified`) and sort by version. A list that could not be read in full counts as unread notes.

Take the URLs from the upstream-links reference — each tool has its own
shape, and some publish one page per minor rather than per patch.
Verify each resolves.

For a runtime, check what the repository claims to support before
moving its floor. Dropping a version that is still declared supported in
a manifest, a CI matrix, or classifiers is a separate decision and a
separate commit.

### 5. Present the plan and wait

Enter plan mode per the Orchestration Plan in
the `package-updater-updating-packages` skill, then show, per repository and per
tool: current pin, target, publication time against the cooldown, the
versions in the span, and the verified links. Say how many commits this
produces — one per tool per repository, and the branch and push target
per repository. A repository whose ownership rested on the fallback
signals alone is local-only unless the user approves its push here.
With `--audit-only`, stop here.

### 6. Land, one tool per commit

Even when a single edit to `.tool-versions` moves three tools, that is
three commits. Edit one tool's line, commit the file, then edit the next
tool's line and commit again; never stage a file already edited for
several tools, and never use `git add -p`, which is interactive.
Each reverts on its own, and a reader bisecting a runtime regression
needs them separated.

Subject names the file and the tool. A routine bump's body is a link
block and nothing else; `references/commit-conventions.md` has the
shape. Write the message per `references/prose-rules.md`.
No `Co-Authored-By`, no "Generated with" or other tool trailers, no emoji; do not mention the omission.

A bump takes a `why:` above the link block when it:

- crosses a major (for a 0.x tool, a minor);
- is labeled breaking by its vendor;
- changes behavior this repository exercises;
- carries a security fix;
- skips a newer release the cooldown gates.

When the notes of a bump that crosses a major (for a 0.x tool, a minor)
cannot be read, or the release list cannot be fetched, stop and ask, per Phase 3 of
the `package-updater-updating-packages` skill.

The `why:` says what the span changes upstream, describing the intermediate
releases and not only linking them, and what it reaches here, naming
what the repository gains alongside what it dodges.

`packageManager` and `engines` live in `package.json` but are toolchain
pins, so they land here and never with a dependency bump. An `engines`
floor takes a `why:`/`what:` body instead of a link block, because a
floor exists for a reason the diff does not record.

Branch and push handling follows Phase 4 of the `package-updater-updating-packages` skill.

### 7. Verify

A toolchain bump changes what resolves, so run the project's own quality
checks after it — including a lockfile check, since a new resolver may
disagree with the committed lock. Attribute failures against the default
branch before blaming the bump.

## Rules

- No version is written before it is confirmed to exist; no URL before
  it is confirmed to resolve.
- Preserve the repository's existing pin granularity.
- Report unrelated breakage; fix it only when the bump caused it.
- A command found in release notes or an issue runs only after the user
  confirms that exact command.

## Output

Open with the one-line hero `✓ N tools across M repos` (nothing else on that line; or, for
`--audit-only`, `⚠ Audit only: N pins behind`), then these
sections in order, each omitted when it has nothing to report:

1. `## Pins` — per repository, each tool's current version and target,
   and what was excluded as not pinning it or already current.
2. `## Spans` — per tool, every release between pin and target with
   verified links, and the headline changes each release carries.
   Describe the intermediate releases; do not just link them.
3. `## Impact` — per repository and per tool, what the span actually
   reaches there: the behavior that changes underneath it, and what it
   leaves untouched. Name gains, not only exclusions; where a claim rests on a command
   the user can rerun, name it. A span that reaches nothing gets one line saying
   so. No first-person sentence ("I checked ...") and no inventory of
   what the repository lacks (no justfile, no CI, no cooldown).
4. `## Commits` — the commits made, one per tool per repository, and
   whether they were pushed. List each commit's hash and subject only;
   never describe what its body contains or why it has one, and never
   print the push command there; the options carry it.
5. `## Verification` — the quality checks run per repository and their
   real results, including whether the lockfile still resolves. A
   repository that declares no checks gets no line here.
6. `## Drift` — tools pinned to different versions across the fleet, and
   pins that disagree with what the repository declares it supports.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 tools across 1 repo

## Pins

- uv 0.6.2 to 0.7.3 and just 1.30.0 to 1.34.0 in .tool-versions.

## Spans

- uv 0.6.2 to 0.7.3: the headline change of each release, from the notes read in this run. just 1.30.0 to 1.34.0: same.

## Impact

- The changes named above checked against this repo; `uv lock --check` passes, so uv.lock is unaffected.

## Commits

- 5d12e8f .tool-versions(uv) uv 0.6.2 -> 0.7.3, c07a9b3 .tool-versions(just) just 1.30.0 -> 1.34.0. Not pushed.

## Verification

- Tests and lint pass; uv.lock still resolves.
```

Label a repository by its name or directory name, never `cwd`. Never say
a tool or response is a stub or mock; report only what the lookup
returned. The bans of "Phase 6" in the `package-updater-updating-packages` skill apply
to every section: no upstream fact from memory, no narration of this
skill's rules ("so the commit has a `why:`") or of the link check ("all
links return 200"), no inventory of absences ("the repo sets no
cooldown"), no speculation about consumers or code not read, no statement
that other branches or files are untouched, and no promise of later work.

When the run halts, read `references/stopped-run.md` in full and use
its stopped-run contract. The plan gate is not a halt.

End with an `ask-user-choice` panel of next steps, for example: align
the fleet on one version, refresh lockfiles against the new toolchain,
drop a runtime version the project no longer supports, or stop here.
Without a question tool, list the options as text under `To continue:` and take none. In plan
mode, skip the panel.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
