# release

Cut and bump releases safely (no automatic push/tag). Rolls out releases
downstream with CI verification.

Discovers procedures dynamically: version files, lockfiles, changelog formats,
MIGRATION files, and quality gates (`AGENTS.md` / `CLAUDE.md`).

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install release@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add release@skills
```

Claude Code uses a leading slash (`/release:…`). Codex omits it (`release:…`).

## Components

### `/release:cut <version> [--push] [--tag] [--push-tag]`

Cuts a release: bumps versions, refreshes lockfiles, dates changelogs, runs
quality gates, and commits.

**Safety Model (Requires Explicit Flags)**:
- **Default**: Commit stays local (no push/tag).
- **`--push`**: Pushes commit.
- **`--tag`**: Creates local tag `v<version>`.
- **`--push-tag`**: Pushes tag (often triggers publish workflow).

Unused flags print as ready-to-run commands. Refuses unprompted tagging if
forbidden by `AGENTS.md`.

### `/release:bump [patch|minor|major|prerelease|final|<version>]`

Like `cut`, but calculates the next version first based on current version,
tags, and changelog headers. Asks on ambiguity.

### `/release:update-downstream-packages <package> [<version>]`

Rolls out published releases to local consumer repos.
- Syncs trunk, updates pins, re-locks, and commits.
- Verifies CI with `gh`.
- Requires confirmation before mutating.
- `--no-push` keeps commits local.

## Shared reference

See `references/release-conventions.md` for discovery procedures, templates,
and safety contracts.

## Prerequisites

- **git** and **gh**.
- The target project's toolchain (as required by quality gates).
