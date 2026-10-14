# package-updater

Update dependencies and toolchains across repositories. Commits
toolchain, named bumps, and lockfile refreshes separately with release
notes cited, and honors a configured supply-chain cooldown.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install package-updater --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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
  `mise.toml`, `packageManager` and `engines`, one tool per commit.
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

## Out of Scope

Handled by sibling plugins:
- GitHub Actions `uses:` pins → `/github-actions:update-actions`
- ruff's floor and rule fallout → `/ruff:bump`
- Terraform versions, providers, and lock files → `/terraform:bump-provider`, `/terraform:bump-terraform` and `/terraform:refresh-lock`

## Ecosystem coverage

The uv, pnpm, npm, Yarn, Cargo, Poetry, pip and Go procedures come from each
tool's own documentation. The plugin proposes the command and waits for
confirmation before the first run in a repository. Eval cases cover
toolchain and named-package bumps, audit scope, fork and ownership
exclusion, cooldown stops, feature-branch worktrees and failed checks.
Ruby, PHP, Java, bun and deno projects are not covered.

## Prerequisites

- git
- python3 (3.9 or newer): runs `scripts/repo_facts.py`, which reports
  fork signal, default branch and pins per repository.
- jq: reads registry responses for the cooldown check.
- curl and network access: link checks and the cooldown check read
  release pages and registries.
- Ecosystem tooling: `uv`, `pnpm`, `ncu`, `npm`, `cargo`, `go`, or
  `mise` (auto-detected).
- gh: for issue creation and GitHub release URL verification.
