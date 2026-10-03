# research

Research a topic or assess a decision so the work outlives the session. Each
run lands in a dated folder, each claim rests on a captured and pinned source,
later runs build on earlier ones, and reports lead with the answer. The plugin
also clones a project's dependencies at the versions it installs.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install research@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add research@skills
```

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Foray | `/research:foray` | `research:foray` | Start, resume, or check a research topic or assessment; routes to the steps below |
| Assess | `/research:assess` | `research:assess` | Rate a decision against criteria fixed up front and reach a verdict |
| Status | `/research:status` | `research:status` | Every topic: latest run, source states, open questions, next action |
| Continue | `/research:continue` | `research:continue` | Carry sources into today's run, re-verify, then fill gaps or expand scope |
| Verify | `/research:verify` | `research:verify` | Re-check sources, look for missed ones, lint the report |
| Report | `/research:report` | `research:report` | Write the report: answer first, sources and exhibits last |
| Study Dependencies | `/research:deps` | `research:study-deps` | Clone deps and create version-pinned worktrees in `~/study/` |

Of the topic skills, `foray` is the only one the model picks up on its own,
from requests like "research how SQLite WAL handles checkpoints and keep the
sources". The others run when you name them, and each hands its step to
`foray`: `/research:verify x` is `/research:foray verify x`.

## Topics

A topic lives in one folder per run:

```text
<root>/<YYYY-MM-DD>/<namespace>/<topic>/
├── index.md          question, scope, open questions, log
├── report.md
├── data/  charts/
└── references/
    ├── sources.jsonl  one row per source version: url, ref, author, retrieved, sha256
    ├── checks.jsonl   re-verification results
    ├── S<n>-<title>.md  a card per source: its provenance, then your notes
    └── raw/           captures exactly as retrieved
```

The root defaults to `~/Documents`, or the Windows Documents folder on WSL.
The default is never the temp directory; `--root` puts it anywhere else.

- **Same day:** reopening returns the same run and changes nothing.
- **A later day:** a new run. Sources, captures, and notes carry forward,
  marked unverified until re-checked. Derived numbers and the report stay
  behind.
- **`--resume`:** keep working in the latest run, for work that spans days in
  one place.
- **Audience:** private, internal, or public. A scan blocks local paths and
  emails, and at wider audiences names and ticket ids, before a report ships.

[references/layout.md](references/layout.md) is the full contract, including
the part other plugins honor when they write dated output.

## The script

The skills drive `scripts/topic.py`, a standard-library Python 3.9+ script.
Every command prints JSON; `--help` lists the options.

Open today's run of a topic:

```console
$ python3 plugins/research/scripts/topic.py open \
    --topic sqlite-wal \
    --subject "SQLite WAL"
```

Record a source and download its capture:

```console
$ python3 plugins/research/scripts/topic.py add \
    --run ~/Documents/2026-10-03/research/sqlite-wal \
    --url https://sqlite.org/wal.html \
    --ref 3.46.0 \
    --kind vendor \
    --fetch \
    --quote "readers do not block writers"
```

Re-check every source against its capture and its live URL:

```console
$ python3 plugins/research/scripts/topic.py verify \
    --run ~/Documents/2026-10-03/research/sqlite-wal
```

The other commands are `prior`, `status`, `scan`, `find`, `links`,
`sources`, `claims`, `lint-report`, and `chart`.

## Study Dependencies

Separate from topics: clone a project's dependencies at the versions it
installs, to read their source. A topic can then cite that source at its tag.

### How It Works

1. **Detect tools**: Checks for `rg`, `fd`, `jq`.
2. **Scan manifests**: Finds `package.json`, `pyproject.toml`, `Cargo.toml`, etc.
3. **Filter**: Applies user filter (package, "all", category).
4. **Resolve repos**: Uses metadata, registry, or search.
5. **Confirm**: Presents plan for approval.
6. **Clone**: Clones/fetches to `~/study/<language>/<repo>/`.
7. **Resolve version**: Matches tags or branches (prefers lockfiles).
8. **Create worktree**: Pins to resolved version.
9. **Report**: Summarizes results.

### Supported Manifests

| Manifest | Language | Lockfiles |
|----------|----------|-----------|
| `package.json` | `typescript` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock` |
| `pyproject.toml` | `python` | `uv.lock`, `poetry.lock`, `requirements.txt` |
| `Cargo.toml` | `rust` | `Cargo.lock` |
| `go.mod` | `golang` | `go.sum` |
| `Gemfile` | `ruby` | `Gemfile.lock` |
| `mix.exs` | `elixir` | `mix.lock` |
| `build.gradle` / `build.gradle.kts`| `java` | `gradle.lockfile` |
| `pom.xml` | `java` | — |

### Version Tag Resolution

Prioritizes: exact tags (`5.2.0`), `v`-prefixed, scoped, crate-style, minor
branches, major branches.

### Arguments

| Flag | Effect |
|------|--------|
| `--lang <language>` | Override auto-detected language |
| `--no-worktree` | Clone only, no worktree |

```console
/research:deps vite
```

```console
/research:deps all
```

```console
/research:deps dev
```

```console
/research:deps react --lang typescript
```

```console
/research:deps tokio --no-worktree
```

### Study Directory Layout

Clones structure under `~/study/`:
- **Main Clone**: `~/study/<language>/<repo>/`
- **Pinned Worktree**: `~/study/<language>/<repo>-<version>/`

Monorepos clone once, with worktrees containing all packages.

## Prerequisites

- **python3** 3.9 or newer, for topics.
- **git**, and a project with a supported manifest, for dependency study.
