# release

Cut and bump releases safely (no automatic push/tag). Rolls out releases
downstream with CI verification.

Discovers procedures dynamically: version files, lockfiles, changelog formats,
MIGRATION files, and quality gates (`AGENTS.md` / `CLAUDE.md`).

## Installation

In Claude Code, add the marketplace:

```console
$ /plugin marketplace add tony/skills
```

Install the plugin:

```console
$ /plugin install release@skills
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

**Safety Model (Requires Explicit Flags)**:
- **Default**: Commit stays local (no push/tag).
- **`--push`**: Pushes commit (`git push --no-follow-tags`).
- **`--tag`**: Creates local annotated tag `v<version>`.
- **`--push-tag`**: Pushes that tag (often triggers publish workflow).
  Requires `--tag` in the same run; alone it is refused before anything
  runs.

Only the literal flags authorize these steps. A question-panel answer
never does. The run stops at the first failed commit or push and never
pushes a tag after a failed commit push. Unused flags print as
ready-to-run commands. A flag authorizes its step even when the target
repo's `AGENTS.md` reserves tags for a human.

`Bash` is pre-approved on these skills, so the guard against an
unwanted tag or push is the skill text and your own permission rules,
not a tool restriction.

### `/release:bump [patch|minor|major|prerelease|final|<version>]`

Like `cut`, but calculates the next version first based on current version,
tags, and changelog headers. Asks on ambiguity.

### `/release:update-downstream-packages <package> [<version>] [--roots <glob>...] [--no-push]`

Rolls out published releases to local consumer repos.
- Syncs trunk, updates pins, re-locks, and commits.
- Verifies CI with `gh`.
- Requires confirmation before mutating.
- `--roots` names the directories that hold your checkouts.
- `--no-push` keeps commits local.

## Shared reference

`references/release-conventions.md` holds the discovery procedures and
templates.

## Prerequisites

- **git** and **gh**.
- The target project's toolchain (as required by quality gates).
