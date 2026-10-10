# release

Cut and bump releases safely (no automatic push/tag). Rolls out releases
downstream with CI verification.

Discovers procedures dynamically: version files, lockfiles, changelog formats,
MIGRATION files, and quality gates (`AGENTS.md` / `CLAUDE.md`).

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install release --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install release@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add release@skills
```

Claude Code uses a leading slash (`/release:…`). Codex omits it (`release:…`).

## Components

### `/release:cut <version> [--push] [--tag] [--push-tag]`

Cuts a release: bumps versions, refreshes lockfiles, dates changelogs, runs
quality gates, and commits.

Safety model (requires explicit flags):
- Default: Commit stays local (no push/tag).
- `--push`: Pushes the release commit to the remote's single push URL, by remote
  name with one explicit `commit:branch` refspec, then reads the branch back.
- `--tag`: Creates a local annotated tag at the verified release commit: the repo's
  tag prefix (`v` when it has none) plus the version. Signing failures stop the run.
- `--push-tag`: Pushes that tag object (often triggers publish workflow) and reads
  back the tag object and its peeled commit. Requires `--tag` in the same run;
  alone it is refused before anything runs.

Only the literal flags authorize these steps. A question-panel answer
never does. The run stops at the first failed commit or push and never
pushes a tag after a failed commit push. Unused flags print as
ready-to-run commands. A flag authorizes its step even when the target
repo's `AGENTS.md` reserves tags for a human.

The release commit must have exactly the gated bytes, one parent on the
synchronized base and no tracked changes. A hook that changes committed bytes sends the
run back through the gates before any tag or push. A remote with several push URLs,
credentials in its URL, rewrite rules or a mirror setting is refused.

`Bash` is pre-approved on these skills, so the guard against an
unwanted tag or push is the skill text and your own permission rules,
not a tool restriction.

### `/release:bump [patch|minor|major|prerelease|final|<version>] [--push] [--tag] [--push-tag]`

Like `cut`, but calculates the next version first based on current version,
tags, and changelog headers. Asks on ambiguity.

### `/release:update-downstream-packages <package> [<version>] [--roots <glob>...] [--push]`

Rolls out published releases to local consumer repos.
- Syncs trunk, updates pins, re-locks, and commits.
- Verifies CI with `gh`.
- Requires confirmation before mutating.
- `--roots`: names the directories that hold your checkouts.
- `--push`: pushes the commits to trunk; without it they stay local.

Read-only discovery uses `scripts/consumer_inventory.py` to inventory
repositories and inspect branch inputs. Pin edits use `scripts/bump_pin.py`, which
changes only dependency declarations in `pyproject.toml`, requirements files and
`package.json`. Verified commits and pushes use `scripts/publish.py`. The scripts use
only Python's standard library.

## Shared reference

`references/release-conventions.md` holds the discovery procedures and
templates.

## Prerequisites

- git, gh and ripgrep (`rg`).
- python3 (3.9 or newer) on `PATH`, for the bundled scripts.
- POSIX process groups for downstream repository discovery, checkout checks and
  publication timeouts.
- The target project's toolchain (as required by quality gates).
