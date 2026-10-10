# Agent history

## Contents

- The state-database rule
- Detecting native compression support
- Without verified native archival support
- Where history lives

Agent transcripts are the one class of data on a developer machine that
no build, no download, and no reinstall can regenerate. Treat every
store here as protected by default. Reclaim from it only through the
owning tool's own archival path, or by proving a copy redundant.

## The state-database rule

Some agent CLIs index sessions in a database and reconcile it against
the filesystem; check whether the tool does. Where it does, renaming,
moving, or compressing a transcript by hand can orphan a session even
when every byte survives.

Before touching any transcript, establish two things:

- **The discovery glob.** Establish the tool's filename pattern from
  documented or tested behavior, not the extensions of existing files.
- **Whether a state DB exists.** Check how the tool updates it after
  importing, renaming, or archiving a session.

Run `<tool> --help` as a standalone command and read the tool's docs first.
Retain its exit status and unfiltered output: a missing executable or an
empty filtered result cannot establish what help lists. When valid help
and documentation are silent, binary strings can locate implementation
clues; leave the store unchanged until discovery and indexing are verified:

```console
$ strings -n 6 <binary> | rg -o '\*\.jsonl|state_db|thread.store|archive[a-z_]*'
```

## Detecting native compression support

Prefer the tool's documented archival path, checking whether archived
sessions remain resumable. These signals can guide investigation but
do not establish that capability:

- A **codec linked in**: a compression library's name or its decoder
  error strings.
- A **literal extension** the tool constructs: `jsonl.zst`, `.jsonl.gz`.
- An **archive routine**: a compress or archive code path or job that
  reports what it compressed and skipped.

A codec alone proves nothing: binaries link zstd and gzip for HTTP
transport and tarballs. Strings are investigation clues, not proof
that a tool can resume a compressed transcript.

Use documentation or a disposable-transcript test for claims about
resumability before proposing a change to the store.

```console
$ strings -n 6 <binary> | rg -o '[a-z_]*compress[a-z_]*'
```

## Without verified native archival support

Unknown archival support is a failed proof. After measuring the store's
allocated size, stop this tier: leave originals and their index intact
and use the blocked shape. Do not measure or
project a compression yield without a verified archival path.

The result sentence is: "Archival support is unverified, so the originals
remain unchanged." `Measured` gives the allocated size and its filesystem.
`Not measured` is "Discovery, resumability, and index updates for compressed
transcripts are unverified." `To continue` asks for the owning tool's
documented archival behavior. These fields contain no hypothetical tool
behavior, gzip command, backup offer, or projected saving.

Where native archival behavior is verified, measure that tool's output
in a disposable copy, report its documented access tradeoff, and let the
user choose a cutoff. Compare allocated sizes, not only stream lengths;
age alone never authorizes modifying history.

## Where history lives

Discover paths rather than trusting this list; tools relocate their
stores between releases.

Common roots include `~/.codex/sessions`, `~/.claude/projects`,
and per-tool state under `~/.local/state`.
On WSL, the Windows-side profile holds a second, independent set.

Two reclaimable classes of file sit *beside* history and are mistaken
for it:

- **Debug logs** — inspect their contents; a name such as `logs*.sqlite`
  does not prove that a database contains only disposable diagnostics.
- **Workspace snapshots** — inspect for build output, then use the
  owning tool's prune mechanism if it can preserve the checkpoint's
  recovery behavior. A nested cache name does not justify editing a
  snapshot store by hand.

Measure the artifact share before classifying a snapshot store. With
GNU coreutils:

```console
$ find <store> \
    -type d \( -name target -o -name node_modules -o -name .venv \) \
    -prune \
    -print0 \
  | du -sch --files0-from=- \
  | tail -1
```

BSD/Darwin `du` has no `--files0-from`, so sum the per-directory sizes
instead. This reports GiB, and a snapshot store that hardlinks across
directories will read high, since each batch dedups only within itself:

```console
$ find <store> \
    -type d \( -name target -o -name node_modules -o -name .venv \) \
    -prune \
    -print0 \
  | xargs -r -0 du -sk \
  | awk '{total += $1} END {printf "%.1f GiB\n", total / 1048576}'
```
