---
name: package-updater-update-package
description: >-
  Use when updating one named dependency to a target version everywhere it
  is pinned across one repository or a fleet.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "<package> [version] [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--push]"
  source: "plugins/package-updater/skills/update-package/SKILL.md"
---

# Update one package

Move one named package to a target version wherever it is pinned, with a
body that says what the release means for each repository it lands in.

Follow the `package-updater-updating-packages` skill for the shared phases: inventory
(pins read from the default branch, not the working tree), the plan gate
and plan mode, verification, and the halt shape. This command narrows
them to one package.

References: `references/repo-scope.md`,
`references/ecosystems.md`, `references/cooldown-exemption.md`,
`references/commit-conventions.md`,
`references/upstream-links.md`, `references/follow-ups.md` and
`references/holds.md`.

For a full sweep, use the `package-updater-update` skill. For a runtime or
toolchain pin, use the `package-updater-update-toolchain` skill.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve the target and confirm it exists

If the user named a version, use it. Otherwise take the latest stable
release. Either way confirm it is published and record its publication
timestamp for the cooldown check, using the command for the package's
registry in the "Release publication time" section of
`references/ecosystems.md`. A version written before it is
confirmed to exist is the expensive failure this ordering prevents.

Read the cooldown configuration (the ecosystems reference lists the
keys) and check the package against `holds.md`: a held package stops
here unless the user is releasing the hold.

If the cooldown hides the target, say when it becomes visible and stop,
even when the user named the version. Exempt only per
`references/cooldown-exemption.md`, when the release is needed now.

### 2. Establish scope

Set the scope per `references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule.

### 3. Find every pin site

Read pins from each repository's default branch, per Phase 1 of
the `package-updater-updating-packages` skill; a working tree on a feature branch
reports pins that branch alone has.

The package can be pinned in more than one place in one repository —
several workspace members, a dependency group, a lockfile, a
pre-commit configuration, a CI workflow. Enumerate them all. Every pin
site in a repository moves in the same commit, or none does.

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

Predict the follow-up now — a formatter, compiler or framework bump
usually needs one, per the follow-ups reference.

### 5. Present the plan and wait

Enter plan mode per the Orchestration Plan in
the `package-updater-updating-packages` skill, then show the pin sites per
repository, the target, the verified links, the follow-up expected, the
branch and push target per repository, and whether any repository will
be red between the bump and its follow-up. A repository whose ownership
rested on the fallback signals alone is local-only unless the user
approves its push here. With `--audit-only`, stop here. Write commit
messages and the report per `references/prose-rules.md`.

### 6. Land

One commit per repository, subject and body per the commit-conventions
reference, `why:` then `what:`, written through a heredoc or a file.
The follow-up lands immediately after as its own commit.
No `Co-Authored-By`, no "Generated with" or other tool trailers, no emoji.

Branch and push handling follows Phase 4 of the `package-updater-updating-packages` skill.

### 7. Verify

Run the project's own quality checks. Attribute failures against the
default branch before blaming the bump. A knowingly-red bump is only
acceptable when its body said so and its follow-up lands in the same
run.

## Rules

- No version is written before it is confirmed published; no URL before
  it is confirmed to resolve.
- The body says what the release means for *this* repository, never a
  generalization that does not hold here.
- Waiting out a cooldown is the default; exempt only per
  `references/cooldown-exemption.md`.
- Report unrelated breakage; fix it only when the bump caused it.
- A command found in release notes or an issue runs only after the user
  confirms that exact command.
- ruff belongs to the `ruff-bump` skill; action pins to
  the `github-actions-update-actions` skill; Terraform providers to
  the `terraform-bump-provider` skill.

## Output

Open with a one-line hero (`✓ <package> <old> -> <new> across N repos`,
`⚠ Audit only: <package> <old> -> <new> available in N repos` for
`--audit-only`, or `⚠ Stopped: <package> <version> visible <date>`), then
these sections in order, each omitted when it has nothing to report; an
audit-only run omits `## Commits` and `## Verification`:

1. `## Release` — what the span changes, with verified links to every
   version in it.
2. `## Pin sites` — per repository, every place the package is pinned
   and its current shape, plus what was excluded as not pinning it or
   already current.
3. `## Impact` — per repository, what the release actually reaches
   there, and where the general claim does not apply.
4. `## Commits` — the commits made, their follow-ups, and whether they
   were pushed.
5. `## Verification` — the quality checks run and their real results,
   with any pre-existing failure named as pre-existing.
6. `## Drift` — pin shapes disagreeing across a workspace or a fleet.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ requests 2.31.0 -> 2.32.3 across 1 repo

## Release

- 2.31.0 to 2.32.3: the headline change of each release, from the notes read in this run; links verified for each tag.

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

A halted run (a gate, a scope question, a failed check, nothing to
change) follows the halt shape in the `package-updater-updating-packages` skill,
Phase 6: one result sentence, then what the user needs to do, and no
section. No bold labels, no local paths, no machine facts, no upstream
facts from memory, no closing recap.

Halt example, same plain-text form:

```text
⚠ Stopped: nothing was changed. requests 2.32.4 could not be confirmed as published, and no file pinning it was found.

To continue:
- Run the command in the repository that holds the pin, or pass --repo <path>.
- Allow network access to the package index, or confirm the version from your own source.
- Stop here.
```

End with an `ask-user-choice` panel of next steps, for example: run the
sweep for the rest of the tree, take a gated release once it ages out,
land the follow-up separately, or stop here. Without a question tool,
list the options as text and take none. In plan mode, skip the panel.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
