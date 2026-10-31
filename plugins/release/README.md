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
quality gates, and commits. A final cut after its own prereleases gets one
changelog section for the net change since the previous final, which replaces
the prerelease sections.

By default the commit stays local. The flags `--push`, `--tag` and `--push-tag`
and the full safety contract (refusals, push URL checks, hooks, signing,
read-back) are defined in `skills/cut/SKILL.md`.

`Bash` is pre-approved on these skills, so the guard against an
unwanted tag or push is the skill text and your own permission rules,
not a tool restriction.

### `/release:bump [patch|minor|major|prerelease|final|<version>] [--push] [--tag] [--push-tag]`

Like `cut`, but calculates the next version first based on current version,
tags, and changelog headers. Asks on ambiguity. Tags are ordered by parsed
version (SemVer or PEP 440), so a graduated prerelease never outranks its final.

### `/release:update-downstream-packages <package> [<version>] [--roots <glob>...] [--push]`

Rolls out published PyPI and npm releases to local consumer repos.
- Syncs trunk, updates pins, re-locks, and commits.
- Verifies CI with `gh`.
- Requires confirmation before mutating.
- `--roots`: names the directories that hold your checkouts.
- `--push`: pushes the commits to trunk; without it they stay local.

Read-only discovery uses `scripts/consumer_inventory.py` to inventory
repositories and inspect branch inputs. Pin edits use `scripts/bump_pin.py`, which
changes only dependency declarations in `pyproject.toml`, requirements files and
`package.json`; a hash-pinned requirement is refused. `scripts/downstream_check.py`
confirms a release on its index and in a consumer's lockfile. Verified commits and
pushes use `scripts/publish.py`. Version order, tags, changelog sections and
leftover-version scans use `scripts/release_plan.py`. The scripts use only
Python's standard library.

## Shared reference

`references/release-conventions.md` holds the discovery procedures and
templates. `references/graduation.md` writes a final's section after its
prereleases.

## Prerequisites

- git, gh and ripgrep (`rg`). The CI steps use `gh run list --commit` with the
  `attempt` JSON field, `gh run watch --exit-status`, `gh run rerun --failed` and
  `gh cache delete`, checked against `gh` 2.102.0.
- python3 (3.14 or newer) on `PATH`, for the bundled scripts.
- POSIX process groups for downstream repository discovery, checkout checks and
  publication timeouts.
- The target project's toolchain (as required by quality gates).
