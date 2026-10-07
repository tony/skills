# Candidate catalog

## Contents

- Regenerable
- Redundant
- Stale but unique
- Protected
- Classification rules
- Ambiguity

Every candidate is classified into exactly one tier. The tier
determines what proof is required before it may be reclaimed, and
whether the user is asked first.

## Regenerable

Content a tool will rebuild or re-download on demand. Deletion costs
time and bandwidth, never data. Reclaim with a single blanket approval.

Package manager content-addressed stores and download caches; compiler
and toolchain caches; browser engine downloads for test harnesses;
build output directories (`target/`, `build/`, `dist/`, `.venv`,
`node_modules`).

Prefer the tool's own command over `rm`. Re-check each with `<tool> --help`:

- npm: `npm cache clean --force`; rebuilt by `npm install`.
- pnpm: `pnpm store prune`; rebuilt by `pnpm install`.
- yarn: `yarn cache clean`; rebuilt by `yarn install`.
- pip: `pip cache purge`; rebuilt by the next install.
- uv: `uv cache prune`; rebuilt by `uv sync`.
- cargo: `cargo clean` inside a project; rebuilt by `cargo build`. It leaves
  `~/.cargo/registry`, which only a cache tool such as `cargo-cache` prunes.
- Go: `go clean -cache` for the build cache, `go clean -modcache` for
  downloaded modules; rebuilt by `go build`.
- Docker: `docker builder prune` for build cache, `docker image prune` for
  dangling images; rebuilt by `docker build` or `docker pull`. Volumes
  (`docker volume ls`) can hold data: classify them stale-but-unique.
- conda, Hugging Face, Gradle, Maven: `conda clean --all`,
  `hf cache prune` and `hf cache rm`, `~/.gradle/caches`, `~/.m2/repository`;
  re-downloaded on demand, so a model or dependency set costs bandwidth
  to restore.
- Homebrew: `brew cleanup`; re-downloaded on demand.
- Playwright browsers: delete the cache directory; `npx playwright install`.
- `node_modules` and `.venv`: delete the directory; `npm ci` or `uv sync`.

System tier (`apt clean`, `journalctl --vacuum-size`, `snap` revisions) is
regenerable but needs root.

Three cautions apply even here:

- **Active projects.** Skip a `.venv`, `node_modules`, `dist/`, or
  `build/` in a project with recent activity or tracked files in that
  directory (`git ls-files <dir>`): `dist/` and `build/` can hold
  committed or hand-made content.
- **Offline capability.** A store that is the only local copy of a
  dependency set stops being regenerable the moment the user is
  offline or the upstream registry removes a version. Ask before
  clearing a store backing a project with a committed lockfile if the
  user has said they work offline.
- **Store generations.** Package managers keep versioned store
  directories side by side across major releases. Older generations
  are dead weight; the current one is hot. Identify which generation
  the installed tool version writes to before deleting any of them.

## Redundant

A second copy of data that exists elsewhere. Safe to delete only once
the copy is *proved* redundant — see `redundancy-proofs.md`. Nothing in
this tier is reclaimed on the strength of a directory's name.

Backup directories, snapshot trees, pre-migration copies, and
duplicated stores under both a real path and a symlinked one.

Resolve symlinks before measuring: a dotfiles-managed directory appears
under two paths, and counting both implies a duplicate that does not
exist.

## Stale but unique

Data that exists nowhere else and is probably unwanted, but only the
user knows. Never delete without an explicit decision on the specific
directory.

Trash and recycle directories; old tool version installs; superseded
toolchain versions; downloads; workspace snapshots from tools no longer
in use.

Present these individually with size, age, and what created them. A
blanket "clear stale data" approval does not cover this tier.

## Protected

Irreplaceable. Never deleted, never compressed without the user
understanding the access tradeoff, never moved without updating the
owning tool's index. See `agent-history.md`.

Agent transcripts and session stores; local databases not backed by a
remote; anything under a path the user has named as history.

## Classification rules

**Default to the highest tier that plausibly applies.** A directory
that might be history is history until proved otherwise. The cost of
over-protecting is a smaller reclaim; the cost of under-protecting is
permanent loss.

**A parent's tier does not propagate to its children.** A protected
history root routinely contains regenerable build artifacts, and a
cache root can contain a store the user has deliberately pinned.
Classify at the level where the content is homogeneous.

**Size does not affect tier.** A 40 GiB cache is regenerable and a
200 MiB transcript store is protected. Ranking by size is for reporting;
it never influences classification.

## Ambiguity

Report a directory that resists classification as unclassified, with its
size, creation source if determinable, and why it is ambiguous. Do not
guess or fold it into a blanket approval group.
