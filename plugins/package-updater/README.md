# package-updater

Update dependencies and toolchains across repositories. Checks the
supply-chain cooldown first, then commits toolchain, named bumps, and
lockfile refreshes separately with release notes cited.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install package-updater@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add package-updater@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/package-updater:update` | `package-updater:update` | Find everything outdated in scope and bring it current, in commit order |
| `/package-updater:update-package <name>` | `package-updater:update-package <name>` | Take one named package to a target version everywhere it is pinned |
| `/package-updater:update-toolchain [tool]` | `package-updater:update-toolchain [tool]` | Move `.tool-versions`, `.nvmrc`, `packageManager` and `engines`, one tool per commit |

- `update`: Update everything outdated. Use `--audit-only` to report
  without writing. Use `--issue github|linear` to file an audit issue
  before starting and work on a derived branch.
- `update-package`: Update a single named package.
- `update-toolchain`: Update a runtime or CLI tool.

Defaults: Current repository, commit on default branch.
Flags:
- `--branch <name>`: Work on a specific branch.
- `--pr`: Open a pull request.
- `--no-push`: Commit locally and stop.
- `--root <dir>`: Sweep every repo beneath a directory.
- `--repo <path|slug>`: Target individual repositories.
- `--owner <name>`: Keep only repos belonging to given accounts.

## The Four Commit Tracks

Dependency commit value lies in reasoning, so work is split into four
tracks:

1. **Toolchain and runtime** — One tool per commit. Every release in the
   span is linked.
2. **Package manager and engines** — `packageManager` and `engines` are
   committed separately from dependencies.
3. **Named package bumps** — One per package (or coupled release train).
   Body includes `why:` and `what:` with verified links.
4. **Bulk lockfile refresh** — Everything routine in one commit with an
   **empty body**. The lockfile diff speaks for itself.

Fallout (e.g., schema bumps, migrations) lands after in a separate commit.

## Supply-Chain Cooldown

Checks for a cooldown before reporting anything as current to prevent
pulling risky, fresh releases. Exemptions are narrow, annotated,
committed alone, and reverted when the block lapses.
- `uv`: Reads `exclude-newer` as a duration.
- `pnpm`: Reads `minimumReleaseAge` (minutes) from `pnpm-workspace.yaml`.
- `npm`: Reads `min-release-age` (days) from `.npmrc`.

## Repository Scope

For `--root` sweeps, the plugin checks forge APIs (`isFork` and
`viewerPermission`).
- Skips forks regardless of ownership.
- **Stops to ask** when signals disagree (e.g., owned repo with only
  agent commits, or contributed-to org repo).

## Discovery Tool Limitations

Clean runs with `ncu` don't mean a current tree, as it misses
`pnpm-workspace.yaml` catalogs, `overrides`, and packages held in
`.ncurc`.

## Holds

Audits `.ncurc` `reject` entries on every sweep:
- Releases holds whose condition has been met.
- Surfaces holds with unrecoverable reasons.
- To properly document a hold, name the condition in the subject:

```
.ncurc: Ignore `@biomejs/biome` 2.3.5 -> 2.3.6 until they fix class methods
```

```
.ncurc: Unignore `@biomejs/biome` (2.3.7 fixed issue)
```

## Out of Scope

Handled by sibling plugins:
- GitHub Actions `uses:` pins → `/github-actions:update-actions`
- ruff's floor and rule fallout → `/ruff:bump`
- Terraform versions, providers, and lock files → `/terraform:bump-provider`

## Components

- **Commands** — `update`, `update-package`, `update-toolchain`.
- **Skill** — `updating-packages` (inventory, discovery, research, plan
  gate, land in order, verify, report).
- **References** — `repo-scope.md`, `ecosystems.md`,
  `commit-conventions.md`, `upstream-links.md`, `follow-ups.md`,
  `holds.md`.

## Prerequisites

- **git**
- **Ecosystem tooling** — `uv`, `pnpm`, `ncu`, `npm`, `cargo`, `go`, or
  `mise` (auto-detected).
- **gh** — For issue creation and GitHub release URL verification.
