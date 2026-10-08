# disk

Safely reclaim disk space. Classifies consumers as regenerable cache, proven
redundant copy, stale-but-unique data (decided per directory), or protected
history, and deletes only what is proven safe.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install disk --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

- `/disk:usage` is a read-only survey of every filesystem layer. It
  classifies what is regenerable, redundant, stale-but-unique, or
  protected, and takes an optional path.
- `/disk:reclaim` runs the full pipeline: survey, classify, plan (needs
  approval), reclaim, verify.

The `disk` skill triggers either flow automatically under disk pressure.

## What it protects

- Agent history: transcripts and session stores are protected unless
  proven redundant or archived through the owning tool.
- Running environments: it never runs environment-halting commands (for
  example `wsl --shutdown`) and prints them for you to run. The WSL and
  Windows commands it prints (`wsl --shutdown`, `Optimize-VHD`) are
  single-platform: they run in Windows PowerShell on the host, not in the
  Linux guest.
- Unproved directories: names like `*-backup-*` or `archive-*` are not
  assumed redundant.

## Inspection scope

- Filesystem layers: compares guest and host footprint to find gaps
  between backing-file size and used space.
- Upstream clones: ranks clones by size and shallow versus full history,
  and checks for unpushed commits and uncommitted changes.

## Prerequisites

- `df`, `du`, `find`, `findmnt` (Linux), `git`, `python3` (3.9 or newer),
  `realpath`, `rsync` (checksum comparison in the redundancy proof), and
  `lsof` or `fuser` (open-file check before deleting)
- WSL only: GNU `find` and `numfmt` (backing-file size) and `fstrim`
  (in-guest trim, run by you)
- (Optional) `dust` for faster surveying, `strings` and `rg` for binary
  inspection, `zstd` for compressing history

Compaction of a live vhdx is documented from Microsoft's pages but has not
been run against one.

Scope is WSL-first: virtual-disk guidance covers WSL, with pointers for
Docker Desktop and Hyper-V. macOS APFS and Time Machine snapshots are not
covered.
