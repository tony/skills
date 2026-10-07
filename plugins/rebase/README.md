# rebase

Rebase onto trunk with file-overlap reading, conflict resolution, and quality-check verification.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install rebase@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add rebase@skills
```

Claude Code uses a leading slash (`/rebase:…`). Codex omits it (`rebase:…`).

## Skills

`/rebase` in Claude Code, `rebase` in Codex: rebase the current branch onto
trunk, resolve conflicts, and run the checks your `AGENTS.md` / `CLAUDE.md`
defines. It never pushes, and it runs only when you invoke it by name.

## Prerequisites

- git 2.30 or newer.
- A remote carrying the trunk branch (the remote's default branch). The skill
  uses the remote the branch tracks, or `upstream` when the branch tracks a
  fork, and asks when the layout is unclear.
