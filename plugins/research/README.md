# research

Research a topic or assess a decision so the work outlives the session. Each
run lands in a dated folder, each claim rests on a captured and pinned source,
later runs build on earlier ones, and reports lead with the answer. The plugin
also clones a project's dependencies at the versions it installs.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install research@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add research@skills
```

Claude Code uses a leading slash (`/research:…`). Codex omits it (`research:…`).

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Foray | `/research:foray` | `research:foray` | Start, resume, or check a research topic or assessment; routes to the steps below |
| Assess | `/research:assess` | `research:assess` | Rate a decision against criteria fixed up front and reach a verdict |
| Status | `/research:status` | `research:status` | Every topic: latest run, source states, open questions, next action |
| Continue | `/research:continue` | `research:continue` | Carry sources into today's run, re-verify, then fill gaps or expand scope |
| Verify | `/research:verify` | `research:verify` | Re-check sources, look for missed ones, lint the report |
| Report | `/research:report` | `research:report` | Write the report: answer first, sources and exhibits last |
| Release | `/research:release` | `research:release` | Pass every check fresh, release the exact report, record decisions, export a bag |
| Study Dependencies | `/research:study-deps` | `research:study-deps` | Clone deps and create version-pinned worktrees in `~/study/` |

Of the topic skills, `foray` is the only one the model picks up on its own,
from requests like "research how SQLite WAL handles checkpoints and keep the
sources". The others run when you name them, and each hands its step to
`foray`: `/research:verify x` is `/research:foray verify x`.

## Topics

A topic is one dated folder per run, `<root>/<YYYY-MM-DD>/<namespace>/<topic>/`,
holding the question, the report, and a `references/` ledger of sources with
their hashes and captures. The root defaults to `~/Documents` (the Windows
Documents folder on WSL); `--root` puts it elsewhere. A later day opens a new run
that carries sources forward, unverified until re-checked; `--resume` keeps
writing in the latest run.

Every finding states its confidence, graded by the kind and number of sources
behind it. Disagreeing sources, searches, and sources that could not be
retrieved are recorded rather than smoothed over. A report ships only when
`check` passes in the same session and the scan for its audience (private,
internal, or public) is clean; `release` keeps the exact version each reader
got, `decide` ties decisions to it, and `status` flags released reports whose
sources have since moved.
[references/analysis.md](references/analysis.md) is the analytic standard.

[references/layout.md](references/layout.md) is the full contract, including
the part other plugins honor when they write dated output.

## The script

The skills drive `scripts/topic.py`, a standard-library Python 3.9+ script.
Every command prints JSON; `--help` lists the options. Fetches connect
directly to the address they vetted, so `HTTPS_PROXY` and `HTTP_PROXY` are
ignored; behind a required proxy, save each page yourself and record it with
`source --file`, then run checks with `--offline`. Examples use the
repo-relative path; an installed plugin runs the script path the skill
resolves.

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
    --kind vendor \
    --fetch \
    --quote "readers do not block writers"
```

Re-check every source against its capture and its live URL:

```console
$ python3 plugins/research/scripts/topic.py verify \
    --run ~/Documents/2026-10-03/research/sqlite-wal
```

Run every ship check fresh before calling a report ready:

```console
$ python3 plugins/research/scripts/topic.py check \
    --run ~/Documents/2026-10-03/research/sqlite-wal
```

The other commands are `prior`, `status`, `scan`, `find`, `links`,
`sources`, `claims`, `lint-report`, `chart`, `searched`, `run`, `conflict`,
`release`, `decide`, and `export`.

## Study Dependencies

Separate from topics: clone a project's dependencies at the versions it
installs, to read their source. A topic can then cite that source at its tag.

### How It Works

The skill reads the project's manifests and lockfiles, resolves each dependency's
source repository, shows the plan, and waits for confirmation before cloning.
Only `https://` repositories are cloned. When no tag matches the resolved version,
the worktree is named for the default branch and its commit, and the report says it
is unpinned. Without an interactive host it prints the plan and stops.

Manifests, lockfiles, and tag resolution follow steps 1 and 6 of
`skills/study-deps/SKILL.md`.

### Arguments

| Flag | Effect |
|------|--------|
| `--lang <language>` | Override auto-detected language |
| `--no-worktree` | Clone only, no worktree |

```text
/research:study-deps vite
```

```text
/research:study-deps all
```

```text
/research:study-deps dev
```

```text
/research:study-deps react --lang typescript
```

```text
/research:study-deps tokio --no-worktree
```

### Study Directory Layout

Clones structure under `~/study/`:
- Main clone: `~/study/<language>/<repo>/`
- Pinned worktree: `~/study/<language>/<repo>-<version>/`

Monorepos clone once, with worktrees containing all packages.

## Prerequisites

- python3 3.9 or newer, for topics.
- git, and a project with a supported manifest, for dependency study.
