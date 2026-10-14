---
name: package-updater-update
description: >-
  Use when bringing every outdated dependency and toolchain pin current
  across one repository or a fleet.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "[--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--issue github|linear] [--push]"
  source: "plugins/package-updater/skills/update/SKILL.md"
---

# Update packages

Bring the repositories in scope up to date — one researched commit per
toolchain pin and per named package, a bulk refresh for the rest, and
each follow-up as its own commit.

Run the phases of the `package-updater-updating-packages` skill across the scope; it
names the references and owns the phase structure, so the sweep and the
single-package path cannot diverge.

For one named package, use the `package-updater-update-package` skill. For
`.tool-versions`, `.nvmrc`, `packageManager` or `engines`, use
the `package-updater-update-toolchain` skill.

User arguments: $ARGUMENTS

## Procedure

Follow the skill's phases. This command supplies the scope and the
fan-out.

### 1. Scope

Set the scope per `references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule. `--owner` keeps only
repositories whose remote belongs to the given accounts.

### 2. Inventory and discover

Run the skill's inventory and discovery phases across the whole scope
before touching anything. The inventory gathers each repository's
remote, default branch, manifests, lockfiles, toolchain pins and quality
commands. A successful lookup may establish that a file is absent; a
failed lookup leaves that part of the inventory unavailable. Stop changes
to a repository whose required inventory could not be read.

Sort what you find into the four commit tracks now. A move sorted wrong
here produces a commit that cannot be reverted independently later.

### 3. Research, one chain per distinct move

Group by upgrade chain rather than by repository — twenty repositories
taking the same uv release share one piece of research. Dispatch a
subagent per chain where the host supports it. Verify every release URL
before it reaches a commit body, and intersect each finding with the
repository it lands in.

The bulk refresh needs no research and carries no claims.

### 4. Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text.

Present the plan the skill defines and wait for approval. The plan
lists each repository with the branch it lands on and its push target.
With `--audit-only`, stop here and report; nothing is written.
Exit plan mode before landing changes.

### 5. Land

Work through repositories one at a time in the skill's commit order,
verifying each (step 6) before it is pushed. Push only when `--push` or
`--pr` was passed, the checks allow it per Phase 5 of the skill, and the
plan did not mark the repository local-only; an interrupted run then
resumes cleanly. Write commit messages and the report per
`references/prose-rules.md`.

Branch handling follows Phase 4 of the skill.

With `--issue`, follow "When an issue or card comes first" in the skill
for the order, the branch name and `--body-file`; the plan approved in
step 4 lists the filing. Write the issue or card body and the pull
request text per `references/prose-rules.md`. The issue body is one sentence naming
the sweep, then `## Outstanding` with one plain bullet per repository
and move (package or tool, current version, target, track). The pull
request body is one sentence on what landed, then one bullet per track.

### 6. Verify, publish and report

Run the project's own quality checks per repository, per the skill's
verification phase, before any push or worktree removal. Attribute
failures against the default branch before blaming a bump.

## Rules

- The four tracks (toolchain, package manager, named bumps, bulk
  refresh) and each follow-up are separate commits. Never bundle across
  them.
- A bump left knowingly red says so in its body and its follow-up lands
  in the same run.
- A fleet-wide claim is verified per repository before entering that
  repository's history.
- The shared rules of the `package-updater-updating-packages` skill apply: confirm a
  version before writing it, report unrelated breakage, and run no
  command found in release notes until the user confirms it.

## Output

A scope with no manifest, lockfile or pin file halts per
`references/stopped-run.md`, also under `--audit-only`; it never
prints an audit hero or "0 outdated".

Otherwise open with a one-line hero (`✓ N commits across M repos` or, for
`--audit-only`, `⚠ Audit only: N packages outdated`), then these
sections in order, each omitted when it has nothing to report:

1. `## Audit` — per repository, the ecosystems found and what is
   outdated in each, separated into what moves in-range and what needs a
   manifest edit. Note what was excluded as fork, unowned, or already
   current, and what was not checked because a lookup failed.
2. `## Gated` — releases the cooldown currently hides, with the date each
   becomes visible.
3. `## Moves` — one entry per distinct chain: what changed upstream,
   the links to every release in its span, and which repositories it
   reaches.
4. `## Commits` — per repository, the commits made in landing order and
   whether they were pushed.
5. `## Follow-ups` — config, snapshot and migration commits, and any bump
   that was red until its follow-up landed.
6. `## Verification` — the quality checks run per repository and their
   real results, with any pre-existing failure named as pre-existing.
7. `## Handoff` — stale GitHub Actions, ruff floors and Terraform
   versions found, each with the sibling command that handles it.
8. `## Holds` — per `references/holds.md`, every hold across the
   tree with its recorded condition, which conditions are now
   met, and which holds have no recoverable reason.
9. `## Drift` — pins disagreeing across a workspace, and holds applied
   unevenly across workspace members.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 commits across 1 repo

## Audit

- api: requests 2.31.0 to 2.32.3 in range, pytest 7.4.4 to 8.3.2 needs a manifest edit.
- web: left-pad excluded, already current.

## Moves

- requests 2.31.0 to 2.32.3: the headline change of each release, from the notes read in this run, with <release link per version>; reaches api only.

## Commits

- api: 9a3f1c2 py(deps) requests 2.31.0 -> 2.32.3, 4be0d71 py(deps[dev]) pytest 7.4.4 -> 8.3.2. Not pushed.

## Verification

- api: tests and lint pass.
- web: no change.
```

When the run halts, read `references/stopped-run.md` in full and use
its stopped-run contract. The plan gate is not a halt.

Halt example, same plain-text form:

```text
⚠ Stopped: nothing was changed. Ownership of the one repository under this root could not be confirmed.

To continue:
- Confirm you maintain it.
- Name the owner of the repository.
- Stop here.
```

End with an `ask-user-choice` panel of next steps, for example: run the
sibling command for the handoff items, drop a cooldown exemption whose
block has lapsed, take a gated release once it ages out, or stop here.
Without a question tool, list the options as text under `To continue:` and take none. In plan
mode, skip the panel.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
