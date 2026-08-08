# Agent history

Agent transcripts are the one class of data on a developer machine that
no build, no download, and no reinstall can regenerate. Treat every
store here as protected by default. Reclaim from it only through the
owning tool's own archival path, or by proving a copy redundant.

## The state-database rule

Modern agent CLIs do not treat the file on disk as the source of truth.
They index sessions in a sidecar database and reconcile it against the
filesystem. Renaming, moving, or compressing a transcript by hand can
therefore orphan a session even when every byte survives.

Before touching any transcript, establish two things:

- **The discovery glob.** What filename pattern does the tool scan for?
  A tool globbing `*.jsonl` will not see `*.jsonl.zst`, whatever codecs
  it links.
- **Whether a state DB exists.** If the tool maintains one, files it
  did not write are invisible to it regardless of location.

Both are recoverable from a shipped binary without source access:

```
strings -n 6 <binary> | rg -o '\*\.jsonl|state_db|thread.store|archive[a-z_]*'
```

## Detecting native compression support

A tool that compresses its own history is always the correct path —
it keeps sessions resumable. Look for three signals together, since any
one alone is misleading:

- A **codec linked in**: `zstd-safe`, `flate2`, `ruzstd` source paths,
  or decoder error strings such as `Unknown frame descriptor`.
- A **literal extension** the tool constructs: `jsonl.zst`, `.jsonl.gz`.
- An **archive routine**: source paths matching `compression.rs`,
  `archive_thread.rs`, or a job emitting counters such as `scanned`,
  `compressed`, `skipped_already_compressed`, `skipped_referenced`.

A codec alone proves nothing. Agent binaries link zstd and gzip for
HTTP transport, OpenTelemetry export, and tarball handling; a runtime's
standard library (Bun, Node) exposes `zstdCompress` to every binary
built on it. Only the extension string plus an archive routine shows
the codec is wired to *history*.

When native support exists, it is usually behind a feature flag. Find
the flag name and enable it in the tool's own config rather than
compressing by hand.

```
strings -n 6 <binary> | rg -o '[a-z_]*compress[a-z_]*'
```

## Compressing without native support

When a tool cannot read compressed history, compression converts the
store from *resumable* to *archive-only*. That is a real cost and the
user decides whether to pay it. Never present compression as free.

State the tradeoff explicitly, then offer a cutoff so recent sessions
stay resumable:

- Sessions older than a cutoff (90 days is a reasonable default) become
  archives, and everything newer stays live.
- Compression is reversible; the tradeoff is only about access, never
  about fidelity.

LLM transcripts compress unusually well — the system prompt, tool
schemas, and file contents repeat across every turn's context. Measure
rather than assume, because inline base64 image data destroys the
ratio.

```
zstd -19 -T0 -c <sample-transcript> | wc -c
```

Check for embedded binary payloads before extrapolating a sample's
ratio across the store.

```
rg -c '"data:image/[a-z]+;base64' <sample-transcript>
```

## Where history lives

Discover paths rather than trusting this list; tools relocate their
stores between releases, and a path may be a symlink into a dotfiles
repository. Resolve symlinks before measuring, or the same bytes get
counted twice under two names.

Common roots include `~/.codex/sessions`, `~/.claude/projects`,
`~/.config/cursor/chats`, and per-tool state under `~/.local/state`.
On WSL, the Windows-side profile holds a second, independent set.

Two classes of file sit *beside* history and are frequently mistaken
for it. Both are reclaimable:

- **Debug logs** — `*-tui.log`, `logs*.sqlite`. These record tool
  internals, not conversation. Multi-gigabyte logs are common.
- **Workspace snapshots** — an agent that checkpoints a working tree
  captures whatever the tree contained, including `target/`,
  `node_modules/`, and build output. The transcript is a rounding error
  against the artifacts. Strip the artifacts and keep the session.

Measure the artifact share before classifying a snapshot store:

```
find <store> -type d \( -name target -o -name node_modules -o -name .venv \) -prune -print0 | du -sch --files0-from=- | tail -1
```
