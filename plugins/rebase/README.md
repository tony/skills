# rebase

Automated rebase onto trunk with conflict prediction, resolution, and quality gate verification.

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
trunk, resolve conflicts, verify quality gates. It never pushes, and it runs
only when you invoke it by name.

## Quality Gates & Design

- Reads `AGENTS.md` / `CLAUDE.md` to discover required checks.
- Does not hardcode linters or test runners; works with whatever the project uses.

## Prerequisites

- git 2.30 or newer.
- A remote carrying the trunk branch (the remote's default branch). The skill
  uses the remote the branch tracks, or `upstream` when the branch tracks a
  fork, and asks when the layout is unclear.
