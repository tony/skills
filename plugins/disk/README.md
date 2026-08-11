# disk

Find what is consuming a machine's disk, and reclaim it without losing
anything that cannot be regenerated.

The failure mode this plugin exists to prevent is not missing some
space. It is deleting a directory whose name suggested it was a
duplicate and which turned out to hold the only copy of something.
Every destructive step is gated on a proof, and the proofs are
specified rather than left to judgment.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/ai-workflow-plugins
```

Install the plugin:

```console
/plugin install disk@ai-workflow-plugins
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/ai-workflow-plugins
```

Install the plugin:

```console
codex plugin add disk@ai-workflow-plugins
```

The skills below are written with Claude Code's leading slash. Codex uses
the same names without it, so `/disk:…` there is `disk:…`.

## Skills

**`/disk:usage`** — survey every filesystem layer and classify what is
reclaimable. Read-only; deletes nothing. Takes an optional path to
focus on.

**`/disk:reclaim`** — the full pipeline through execution: survey,
classify, plan behind an approval gate, reclaim, verify.

The `disk` skill triggers either flow automatically when a conversation
turns to disk pressure.

## What it protects

**Agent history.** LLM transcripts and session stores are treated as
irreplaceable by default. They are reclaimed only through the owning
tool's own archival mechanism, or after one copy is proved redundant
against another. Compression is never presented as free: when a tool
cannot read its own compressed history, compressing converts sessions
from resumable to archive-only, and that tradeoff is the user's call.

**Your running environment.** The plugin never runs `wsl --shutdown`,
`wsl --terminate`, or any equivalent guest-halting command. Those kill
unsaved work across every shell and editor on the machine. Commands
that require a halted environment are printed for you to run, with
their consequences stated.

**Anything unproved.** A directory named `*-backup-*`, `.old`, or
`archive-*` carries no information about whether it is redundant.
Backups diverge as live trees are rotated and pruned, after which the
"backup" holds the only copy of everything the live tree dropped.

## How candidates are classified

Every candidate lands in exactly one tier, and the tier determines what
proof is required before it can be touched.

**Regenerable** — package stores, download caches, build output. A tool
rebuilds it on demand. One blanket approval.

**Redundant** — a second copy of data that exists elsewhere. Deletable
only once a path-set comparison proves the intersection, not merely
that no shared file differs.

**Stale but unique** — trash, superseded toolchains, old tool installs.
Exists nowhere else and is probably unwanted, but only you know.
Decided per directory.

**Protected** — agent transcripts, local databases with no remote.
Never deleted.

## What it looks at

Filesystem layers first, because deleting files inside a virtual disk
frees nothing on the host until the disk is compacted. A guest
reporting ample free space says nothing about the host storing its
backing file, and the gap between a backing file's allocated size and
the guest's used space is often the largest single recovery available —
with no deletion at all.

Directories of upstream clones kept for reading get their own
treatment: clones ranked by size, clones that are not shallow ranked by
how much of their footprint is history nobody reads, and build
artifacts aggregated separately. Nothing there is converted without
first checking for unpushed commits, stashes, and uncommitted changes.

## Prerequisites

`df`, `du`, and `find` are enough. `dust` is used for faster surveying
when present, `rg` for binary inspection when determining a tool's
history format, and `rsync` for checksum-verified merges.
