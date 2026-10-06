# slop

Find AI slop, verbose noise, and brittle references in a branch's commits
or in the tracked files at HEAD, and fix them with reviewable patches.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install slop@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add slop@skills
```

Claude Code uses a leading slash (`/slop:…`). Codex omits it (`slop:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/slop:deslop` | `slop:deslop` | Audit the branch's commits since trunk; resolve through fixup commits and autosquash. |
| `/slop:scan` | `slop:scan` | Audit tracked files at HEAD; land one atomic commit per finding after quality-gate checks. |

Both skills are invoked by name only. They share one signature registry,
one quality-gate discovery procedure, and one tone-calibration step.

## Choosing

Use `/slop:deslop` before opening a PR, when the slop sits in commits
you are about to ship. It rewrites history, so it refuses pushed
branches and branches with merge commits unless told otherwise.

Use `/slop:scan` for slop already on trunk or in long-lived files. It
only adds commits, so it is safe on pushed and shared branches.

## How it works

Both skills run the same detection pipeline: lock the baseline at the
trunk merge-base, discover the project's format, lint, typecheck, and
test commands from `AGENTS.md`, `CLAUDE.md`, and
`.github/CONTRIBUTING.md`, calibrate subjective signals against trunk
history, then run a regex pass and an optional semantic verifier. Both
write a numbered patch series under the git directory first. Nothing changes
until you pass an apply flag and confirm.

`/slop:deslop` writes `deslop/<ts>-<pid>/` under the git directory with a checkpointed
`apply.sh`. `--apply-patches` offers fixup commits on `HEAD`;
`--apply-rebase` also offers an autosquash, with a backup branch first
and quality gates inside the conflict loop.

`/slop:scan` writes `slop-scan/<ts>-<pid>/` under the git directory with `commits.json`.
`--apply` offers the per-finding loop: edit, stage the file, run gates,
commit. A gate failure rolls the file back and the run continues.

## Arguments

Audit the branch since trunk:

```
/slop:deslop
```

Offer fixup commits on `HEAD`:

```
/slop:deslop --apply-patches
```

Offer autosquash, with tests in the conflict loop:

```
/slop:deslop --apply-rebase --run-tests
```

Audit commit messages only, with the strict budget:

```
/slop:deslop --message-only --budget=strict
```

Allow a branch that was already pushed:

```
/slop:deslop --force-rewrite-pushed --apply-rebase
```

Audit the repo without applying anything:

```
/slop:scan
```

Scope to a subdirectory:

```
/slop:scan --paths='src/**'
```

Include the last 50 commits, as advisory findings:

```
/slop:scan --with-history=50
```

Offer the per-finding commit loop:

```
/slop:scan --apply
```

Stop on the first gate failure instead of skipping:

```
/slop:scan --apply --on-fail=stop
```

## Project overrides

`.claude/slop.local.yml` in the repo root changes the registry for both
skills with `replace:`, `append:`, and `delete:` lists of signature ids.
An id may appear under only one key.

## Safety

- Audit first: without an apply flag, nothing changes.
- Tier A findings apply without a per-finding prompt once you pick an
  apply choice; Tier B needs your confirmation per finding; Tier C is
  advisory.
- `/slop:deslop` creates a backup branch before touching history and
  never pushes.
- `/slop:scan` never rewrites history and never touches a file that had
  uncommitted changes when the run started.
- Both stage explicit paths only and never bypass hooks.

## Prerequisites

- **git**
- **Formatter, linter, type-checker**: discovered at runtime from the
  project's conventions files.
