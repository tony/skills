# disk

Safely reclaim disk space. Classifies consumers as cache, redundant copy,
or history, deleting only what is proven safe.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install disk@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add disk@skills
```

*Note: The skills below use Claude Code's leading slash. Codex uses the
same names without it.*

## Skills

- **`/disk:usage`**: Read-only survey of every filesystem layer.
  Classifies what is reclaimable. Takes an optional path.
- **`/disk:reclaim`**: Full pipeline: survey, classify, plan (needs
  approval), reclaim, verify.

The `disk` skill triggers either flow automatically under disk pressure.

## What it protects

- **Agent history**: Transcripts and session stores are protected unless
  proven redundant or archived through the owning tool.
- **Running environments**: Never runs environment-halting commands (e.g.,
  `wsl --shutdown`). Prints such commands for you to run manually.
- **Unproved directories**: Directories like `*-backup-*` or `archive-*`
  are not assumed redundant.

## Classification Tiers

- **Regenerable**: Caches, package stores, build outputs (One blanket
  approval).
- **Redundant**: Secondary copies proven via path-set comparison.
- **Stale but unique**: Trash, old toolchains, superseded installs
  (Decided per directory).
- **Protected**: Agent transcripts, local databases with no remote
  (Never deleted).

## Inspection Scope

- **Filesystem layers**: Evaluates guest vs. host footprint to identify
  gaps in allocated size vs. used space.
- **Upstream clones**: Ranks clones by size and shallow vs. full history.
  Checks for unpushed commits and uncommitted changes.

## Prerequisites

- `df`, `du`, `find`
- (Optional) `dust` for faster surveying, `rg` for binary inspection,
  `rsync` for checksum-verified merges
