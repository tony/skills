# disk

Safely reclaim disk space. Classifies consumers as cache, redundant copy,
or history, deleting only what is proven safe.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install disk@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add disk@skills
```

Claude Code uses a leading slash (`/disk:…`). Codex omits it (`disk:…`).

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
  `wsl --shutdown`). Prints such commands for you to run manually. The
  WSL and Windows commands it prints (`wsl --shutdown`, `Optimize-VHD`)
  are single-platform: they run in Windows PowerShell on the host, not in
  the Linux guest.
- **Unproved directories**: Directories like `*-backup-*` or `archive-*`
  are not assumed redundant.

## Inspection Scope

- **Filesystem layers**: Evaluates guest vs. host footprint to identify
  gaps in backing-file size vs. used space.
- **Upstream clones**: Ranks clones by size and shallow vs. full history.
  Checks for unpushed commits and uncommitted changes.

## Prerequisites

- `df`, `du`, `find`, `findmnt` (Linux), `git`, `python3`, `realpath`,
  `rsync` (checksum comparison in the redundancy proof), and `lsof` or
  `fuser` (open-file check before deleting)
- (Optional) `dust` for faster surveying, `strings` and `rg` for binary
  inspection, `zstd` for compressing history

Scope is WSL-first: virtual-disk guidance covers WSL, with pointers for
Docker Desktop and Hyper-V. macOS APFS and Time Machine snapshots are not
covered.
