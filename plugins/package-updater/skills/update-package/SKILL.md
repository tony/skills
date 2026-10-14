---
name: update-package
description: "Use when updating one named dependency to a target version everywhere it is pinned across one repository or a fleet."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "AskUserQuestion"]
argument-hint: "<package> [version] [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--push]"
disable-model-invocation: true
---

# Update one package

Move one named package to a target version wherever it is pinned, with a
body that says what the release means for each repository it lands in.

Follow `../updating-packages/SKILL.md` for the shared phases: inventory
(pins read from the default branch, not the working tree), the plan gate
and plan mode, verification, and the halt shape. This command narrows
them to one package.

References: `../../references/repo-scope.md`,
`../../references/ecosystems.md`, `../../references/cooldown-exemption.md`,
`../../references/commit-conventions.md`,
`../../references/upstream-links.md`, `../../references/follow-ups.md` and
`../../references/holds.md`.

For a full sweep, use `/package-updater:update`. For a runtime or
toolchain pin, use `/package-updater:update-toolchain`.

User arguments: $ARGUMENTS

## Procedure

### 1. Establish scope

Set the scope per `../../references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule.

### 2. Resolve the target and confirm it exists

If the user named a version, use it. Otherwise take the latest stable
release, with the command for the package's registry in "Latest stable
release" of `../../references/ecosystems.md`. Either way confirm it is published and record its publication
timestamp for the cooldown check, using the command for the package's
registry in the "Release publication time" section of
`../../references/ecosystems.md`. A version written before it is
confirmed to exist is the expensive failure this ordering prevents.

Read the cooldown configuration of each repository in scope (the
ecosystems reference says where to read each tool's setting) and check the package against
`holds.md`: a held package stops here unless the user is releasing the
hold; halt with the hold form in `../../references/stopped-run.md`.

If the cooldown hides the target, read `../../references/stopped-run.md`
and use its cooldown form, even when the user named the version. The reply is that halt alone: no
sentence about the named version, the user's go-ahead, what was left
unchanged, or an exemption. Exempt only per
`../../references/cooldown-exemption.md`, when the release is needed now.

### 3. Find every pin site

Read pins from each repository's default branch, per Phase 1 of
`../updating-packages/SKILL.md`; a working tree on a feature branch
reports pins that branch alone has.

The package can be pinned in more than one place in one repository —
several workspace members, a dependency group, a lockfile, a
pre-commit configuration, a CI workflow. List every tracked line that
names the package with `../../scripts/repo_facts.py --pin-sites <repo>
<name>` (resolve the path from this skill's directory to an absolute
one), then read each hit: a name inside prose or a longer identifier is
not a pin. Every pin site in a repository moves in the same commit, or
none does. A pin owned by a sibling plugin (ruff in pre-commit, an
action in CI) is reported with its sibling command, not moved here.

Note where the pin shapes disagree — an exact pin in one package and a
caret range in another is drift worth reporting even when both resolve
to the same version.

### 4. Research the span once

Read the release notes for every version between the current pin and the
target, not just the endpoint. Collect links per the upstream-links
reference and verify each resolves.

Then, separately per repository, work out what the release actually
reaches. A release note describes the package; only the repository can
say whether the change applies. Where the general claim does not hold,
the body says something different in that repository.

When the notes of a major bump, or a 0.x bump crossing a minor, cannot
be read, stop and ask, per Phase 3 of `../updating-packages/SKILL.md`.

Predict the follow-up now — a formatter, compiler or framework bump
usually needs one, per the follow-ups reference.

### 5. Present the plan and wait

Enter plan mode per the Orchestration Plan in
`../updating-packages/SKILL.md`, then show the pin sites per
repository, the target, the verified links, the follow-up expected, the
branch and push target per repository, and whether any repository will
be red between the bump and its follow-up. A repository whose ownership
rested on the fallback signals alone is local-only unless the user
approves its push here. With `--audit-only`, stop here. Write commit
messages and the report per `../../references/prose-rules.md`.

### 6. Land

One commit per repository, subject and body per the commit-conventions
reference, `why:` then `what:`, written through a heredoc or a file.
The follow-up lands immediately after as its own commit.

Branch handling follows Phase 4 of `../updating-packages/SKILL.md`; a push
waits for step 7 and Phase 5. Pull request text goes through `--body-file`.

### 7. Verify, then publish

Run the project's own quality checks before any push or worktree removal. Attribute failures against the
default branch before blaming the bump. A knowingly-red bump is only
acceptable when its body said so and its follow-up lands in the same
run.

## Rules

- The body says what the release means for *this* repository, never a
  generalization that does not hold here.
- Waiting out a cooldown is the default; exempt only per
  `../../references/cooldown-exemption.md`.
- The shared rules of `../updating-packages/SKILL.md` apply: confirm a
  version before writing it, report unrelated breakage, and run no
  command found in release notes until the user confirms it. Its Scope
  section routes ruff, action pins and Terraform to the sibling plugins.

## Output

Open with a one-line hero (`✓ <package> <old> -> <new> across N repos`,
or `⚠ Audit only: <package> <old> -> <new> available in N repos` for
`--audit-only`; a halt takes its own shape, below), then
these sections in order, each omitted when it has nothing to report; an
audit-only run omits `## Commits` and `## Verification`:

1. `## Release` — what the span changes, with verified links to every
   version in it. Describe each release; never fold them into "the
   notes say the same thing", and never narrate the link check ("all
   links resolved").
2. `## Pin sites` — per repository, every place the package is pinned
   and its current shape, plus what was excluded as not pinning it or
   already current, and what was not checked because a lookup failed.
   Name no ref the pins were read from and no release-age
   setting the repository lacks.
3. `## Impact` — per repository, what the release actually reaches
   there, and where the general claim does not apply. No first-person
   sentence ("I checked ...") and no inventory of what the repository
   lacks (no justfile, no CI, no cooldown).
4. `## Commits` — the commits made, their follow-ups, and whether they
   were pushed. List each commit's hash and subject only; never describe
   what its body contains or the files it touches, and never print the
   push command there; the options carry it.
5. `## Verification` — the quality checks run and their real results,
   with any pre-existing failure named as pre-existing. A repository that
   declares no checks gets no line here.
6. `## Drift` — pin shapes disagreeing across a workspace or a fleet.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ requests 2.31.0 -> 2.32.3 across 1 repo

## Release

- 2.31.0 to 2.32.3: the headline change of each release, from the notes read in this run, with <release link per version>.

## Pin sites

- api: pyproject.toml and uv.lock.
- web: not a Python project, excluded.

## Impact

- api: the changes named above checked against its call sites; only the ones it exercises are claimed.

## Commits

- api: 9a3f1c2 py(deps) requests 2.31.0 -> 2.32.3. Not pushed.

## Verification

- api: tests pass, uv.lock resolves.
```

Label a repository by its name or directory name, never `cwd`. Never say a tool
or response is a stub or mock; report only what the lookup returned. The bans
of "Phase 6" in `../updating-packages/SKILL.md` apply to every section, as do
these: no inventory of absences, no speculation about consumers or code not
read, and no statement that other branches or files are untouched.

When the run halts, read `../../references/stopped-run.md` in full and use
its stopped-run contract. The plan gate is not a halt.

Halt example, same plain-text form:

```text
⚠ Stopped: nothing was changed. requests 2.32.4 could not be confirmed as published.

To continue:
- Confirm the version from your own source.
- Stop here.
```

End with an `AskUserQuestion` panel of next steps, for example: run the
sweep for the rest of the tree, take a gated release once it ages out,
land the follow-up separately, or stop here. Without a question tool,
list the options as text under the label `To continue:` (never "Next steps") and take none. In plan mode, skip the panel.
