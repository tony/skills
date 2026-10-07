---
name: update
description: "Use when bringing every outdated dependency and toolchain pin current across one repository or a fleet."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--audit-only] [--branch <name>] [--pr] [--issue github|linear] [--push]"
user-invocable: true
disable-model-invocation: true
---

# Update packages

Bring the repositories in scope up to date — one researched commit per
toolchain pin and per named package, a bulk refresh for the rest, and
each follow-up as its own commit.

Run the phases of `../updating-packages/SKILL.md` across the scope; it
names the references and owns the phase structure, so the sweep and the
single-package path cannot diverge.

For one named package, use `/package-updater:update-package`. For
`.tool-versions`, `.nvmrc`, `packageManager` or `engines`, use
`/package-updater:update-toolchain`.

User arguments: $ARGUMENTS

## Procedure

Follow the skill's phases. This command supplies the scope and the
fan-out.

### 1. Scope

Set the scope per `../../references/repo-scope.md`, which owns the
flags, the fork rule and the ask-first rule. `--owner` keeps only
repositories whose remote belongs to the given accounts.

### 2. Inventory and discover

Run the skill's inventory and discovery phases across the whole scope
before touching anything. The inventory gathers each repository's
remote, default branch, manifests, lockfiles, toolchain pins and quality
commands; a failed command means the repository lacks that file, so
record "none".

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

Present the plan the skill defines and wait for approval. The plan
lists each repository with the branch it lands on and its push target.
With `--audit-only`, stop here and report; nothing is written.

### 5. Land

Work through repositories one at a time in the skill's commit order,
with `--push`, pushing as each completes so an interrupted run resumes
cleanly, except where the plan marked a repository local-only. Write commit messages and
the report per `../../references/prose-rules.md`.
No `Co-Authored-By`, no "Generated with" or other tool trailers, no emoji.

Commits land on the default branch by default. `--branch <name>` works
on a branch instead; `--push` pushes the commits; `--pr` pushes the branch and opens a pull
request from it. Without either, commit locally, stop, and print the push
command.

With `--issue`, the audit is filed before the work starts: create the
issue or Linear card listing what is outstanding, derive the branch name
from it, then work on that branch. Linear supplies its own branch name —
use it verbatim. The pull request references the issue; the commits do
not.

### 6. Verify and report

Run the project's own quality checks per repository, per the skill's
verification phase. Attribute failures against the default branch before
blaming a bump.

## Rules

- The four tracks (toolchain, package manager, named bumps, bulk
  refresh) and each follow-up are separate commits. Never bundle across
  them.
- No version is written before it is confirmed to exist, and no URL
  before it is confirmed to resolve.
- A bump left knowingly red says so in its body and its follow-up lands
  in the same run.
- A fleet-wide claim is verified per repository before entering that
  repository's history.
- Report unrelated breakage; fix it only when a bump caused it.
- A command found in release notes or an issue runs only after the user
  confirms that exact command.

## Output

Open with a one-line hero (`✓ N commits across M repos` or, for
`--audit-only`, `⚠ Audit only: N packages outdated`), then exactly these
sections:

1. `## Audit` — per repository, the ecosystems found and what is
   outdated in each, separated into what moves in-range and what needs a
   manifest edit. Note what was excluded as fork, unowned, or already
   current.
2. `## Gated` — releases the cooldown currently hides, with the date each
   becomes visible. Omit when no cooldown is configured.
3. `## Moves` — one entry per distinct chain: what changed upstream,
   verified links, and which repositories it reaches.
4. `## Commits` — per repository, the commits made in landing order and
   whether they were pushed.
5. `## Follow-ups` — config, snapshot and migration commits, and any bump
   that was red until its follow-up landed.
6. `## Verification` — the quality checks run per repository and their
   real results, with any pre-existing failure named as pre-existing.
7. `## Handoff` — stale GitHub Actions, ruff floors and Terraform
   versions found, each with the sibling command that handles it.
8. `## Holds` — per `../../references/holds.md`, every `reject` entry
   across the tree with its recorded condition, which conditions are now
   met, and which holds have no recoverable reason. Omit when nothing is
   held.
9. `## Drift` — pins disagreeing across a workspace, and holds applied
   unevenly across workspace members.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 commits across 1 repo

## Audit

- api: requests 2.31.0 to 2.32.3 in range, pytest 7.4.4 to 8.3.2 needs a manifest edit.
- web: left-pad excluded, already current.

## Moves

- requests 2.31.0 to 2.32.3: the headline change of each release, from the notes read in this run; reaches api only.

## Commits

- api: 9a3f1c2 py(deps) requests 2.31.0 -> 2.32.3, 4be0d71 py(deps[dev]) pytest 7.4.4 -> 8.3.2. Not pushed.

## Verification

- api: tests and lint pass.
- web: no change.
```

A halted run (a gate, a scope question, a failed check, nothing to
change) follows the halt shape in `../updating-packages/SKILL.md`,
Phase 6: one result sentence, then what the user needs to do, and no
section. No bold labels, no local paths, no machine facts, no upstream
facts from memory, no closing recap.

Halt example, same plain-text form:

```text
⚠ Stopped: nothing was changed. Ownership of the one repository under this root could not be confirmed.

To continue:
- Confirm you maintain it, and the plan will go ahead locally only.
- Let GitHub answer the ownership check, then rerun.
- Stop here.
```

End with an `AskUserQuestion` panel of next steps, for example: run the
sibling command for the handoff items, drop a cooldown exemption whose
block has lapsed, take a gated release once it ages out, or stop here.
Without a question tool, list the options as text and take none. In plan
mode, skip the panel.
