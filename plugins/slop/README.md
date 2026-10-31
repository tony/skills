# slop

Find AI slop, verbose noise, and brittle references in a branch's commits
or in the tracked files at HEAD, and fix them with reviewable patches.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install slop --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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
you are about to ship. With `--apply-rebase` it rewrites history, requires
`--force-rewrite-pushed` for published commits, and refuses merge commits.

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
`--apply` offers the per-finding loop: apply the patch, run gates and commit
hooks in a disposable worktree, then publish the approved file. A gate or
hook failure leaves the checkout untouched. Edit
`commits.json` first, then re-run with `--apply --from=<run-dir>` to commit
your wording.

## Arguments

Audit the branch since trunk:

```text
/slop:deslop
```

Offer fixup commits on `HEAD`:

```text
/slop:deslop --apply-patches
```

Offer autosquash, with tests in the conflict loop:

```text
/slop:deslop --apply-rebase --run-tests
```

Audit commit messages only, with the strict budget:

```text
/slop:deslop --message-only --budget=strict
```

Let `--apply-rebase` rewrite a branch that was already pushed:

```text
/slop:deslop --force-rewrite-pushed --apply-rebase
```

Audit the repo without applying anything:

```text
/slop:scan
```

Scope to a subdirectory:

```text
/slop:scan --paths='src/**'
```

Include the last 50 commits, as advisory findings:

```text
/slop:scan --with-history=50
```

Offer the per-finding commit loop:

```text
/slop:scan --apply
```

Commit a series you reviewed, keeping your edits to `commits.json`:

```text
/slop:scan --apply --from=<run-dir>
```

Stop on the first gate failure instead of skipping:

```text
/slop:scan --apply --on-fail=stop
```

## Project overrides

`.claude/slop.local.yml` in the repo root changes the registry for both
skills with `replace:`, `append:`, and `delete:` lists of signature ids.
An id may appear under only one key. The file is read as a YAML subset:
top-level scalars and lists of flat mappings, quoted or plain scalars, and
single-line `[a, b]` lists. Anchors, tags, nested mappings, and multi-line
flow lists exit with an error naming the line.

## Standalone detector

`scripts/slop_detect.py` runs without a model for CI or a pre-commit hook.
It prints one JSON object of findings from `messages` (commit messages),
`diff` (a unified diff on stdin), or `files` (tracked paths), and exits 2
on a malformed registry. For example, check the branch's commit messages:

```console
$ git log -z --format=%H%x1f%B origin/main..HEAD | python3 scripts/slop_detect.py messages \
    --registry references/signatures.yml
```

## Safety

- Audit first: without an apply flag, nothing changes.
- Tier A findings apply without a per-finding prompt once you pick an
  apply choice; Tier B needs your confirmation per finding; Tier C is
  advisory.
- A project whose `AGENTS.md`, `CLAUDE.md`, or `CONTRIBUTING.md` requires
  AI-assistance disclosure keeps attribution footers as a Tier B proposal.
- `/slop:deslop` creates a backup branch before touching history and
  never pushes.
- `/slop:scan` checks the live target before publication and preserves
  unrelated staged, unstaged, and untracked work. Gates and commit hooks
  run in isolation; a blocked publication retains a recovery branch.
- Both stage explicit paths only and never bypass hooks.

## Prerequisites

- git
- python3 (3.14 or newer): runs the regex matcher and the `apply.sh` renderer
- Formatter, linter, type-checker: discovered at runtime from the
  project's conventions files.
