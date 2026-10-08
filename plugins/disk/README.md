# disk

Safely reclaim disk space. Classifies consumers as regenerable cache, proven
redundant copy, data needing a directory-specific decision, or protected
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
  classifies what is regenerable, redundant, needs a decision, or
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

- Filesystem layers: measures guest usage and backing-file apparent size
  separately from host allocation; their gap is not a recovery estimate.
- Upstream clones: ranks clones by size and shallow versus full history,
  and checks for unpushed commits and uncommitted changes.

## Prerequisites

- `df`, `du`, `find`, `findmnt` (Linux), `git`, `python3` (3.9 or newer),
  `realpath`, `rsync` (checksum comparison in the redundancy proof), and
  `lsof` (open-file check before deleting; any warning refuses removal)
- WSL only: GNU `find` and `numfmt` (backing-file size) and `fstrim`
  (in-guest trim, run by you)
- (Optional) `dust` for faster surveying, `strings` and `rg` for binary
  inspection

Compaction of a live vhdx is documented from Microsoft's pages but has not
been run against one.

Open-file checks cover processes visible to the caller, not privileged or
hidden processes. They do not lock out new opens or mount changes. Stop
active owners first or use the owning tool's prune mechanism.

Scope is WSL-first: virtual-disk guidance covers WSL, with pointers for
Docker Desktop and Hyper-V. macOS APFS and Time Machine snapshots are not
covered.
