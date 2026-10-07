# package-updater

Update dependencies and toolchains across repositories. Checks the
supply-chain cooldown first, then commits toolchain, named bumps, and
lockfile refreshes separately with release notes cited.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install package-updater@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add package-updater@skills
```

Claude Code uses a leading slash (`/package-updater:…`). Codex omits it (`package-updater:…`).

## Skills

Each skill runs as `/package-updater:<name>` in Claude Code and
`package-updater:<name>` in Codex.

- `update`: Find everything outdated in scope and bring it current, in
  commit order. Use `--audit-only` to report without writing. Use
  `--issue github|linear` to file an audit issue before starting and
  work on a derived branch.
- `update-package <name>`: Take one named package to a target version
  everywhere it is pinned.
- `update-toolchain [tool]`: Move `.tool-versions`, `.nvmrc`,
  `packageManager` and `engines`, one tool per commit.
- `updating-packages`: The shared procedure the three above follow
  (inventory, discovery, research, plan gate, land in order, verify,
  report). Claude invokes it when packages are out of date.

Defaults: Current repository, commit on default branch, no push.
Flags:
- `--branch <name>`: Work on a specific branch.
- `--pr`: Open a pull request.
- `--push`: Push the commits; without `--push` or `--pr`, commit locally and print the push command.
- `--root <dir>`: Sweep every repo beneath a directory.
- `--repo <path|slug>`: Target individual repositories.
- `--owner <name>`: Keep only repos belonging to given accounts.

## The Four Commit Tracks

Dependency commit value lies in reasoning, so work is split into four
tracks:

1. Toolchain and runtime: one tool per commit. Every release in the
   span is linked.
2. Package manager and engines: `packageManager` and `engines` are
   committed separately from dependencies.
3. Named package bumps: one per package (or coupled release train).
   Body includes `why:` and `what:` with verified links.
4. Bulk lockfile refresh: everything routine in one commit with an
   empty body. The lockfile diff speaks for itself.

Fallout (e.g., schema bumps, migrations) lands after in a separate commit.

## Supply-Chain Cooldown

Checks for a cooldown before reporting anything as current to prevent
pulling risky, fresh releases. Exemptions are narrow, annotated,
committed alone, and reverted when the block lapses.

Each tool names, scales and enforces its cooldown differently. The
plugin reads the setting and its units from the installed tool's help and
documentation at run time; the keys the reference names are search
hints, not settings to copy.

## Repository Scope

For `--root` sweeps, the plugin checks forge APIs (`isFork` and
`viewerPermission`).
- Skips forks regardless of ownership.
- Stops to ask when signals disagree (e.g., owned repo with only
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

```text
.ncurc: Hold `@biomejs/biome` at 2.3.5 until class-method fix
```

```text
.ncurc: Unignore `@biomejs/biome` (2.3.7 fixed issue)
```

## Out of Scope

Handled by sibling plugins:
- GitHub Actions `uses:` pins → `/github-actions:update-actions`
- ruff's floor and rule fallout → `/ruff:bump`
- Terraform versions, providers, and lock files → `/terraform:bump-provider`

## Ecosystem coverage

uv, pnpm, npm and Cargo flows are exercised. The Poetry, pip and Go
procedures come from each tool's own documentation and are experimental:
the plugin proposes the command and waits for confirmation before the
first run in a repository.

## Prerequisites

- git
- curl and network access: link checks and the cooldown check read
  release pages and registries.
- Ecosystem tooling: `uv`, `pnpm`, `ncu`, `npm`, `cargo`, `go`, or
  `mise` (auto-detected).
- gh: for issue creation and GitHub release URL verification.
