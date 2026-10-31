# rebase

Rebase onto trunk with file-overlap reading, conflict resolution, and quality-check verification.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install rebase --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

`/rebase:rebase` in Claude Code, `rebase:rebase` in Codex: rebase the current
branch onto trunk, resolve conflicts, and run the checks your `AGENTS.md` / `CLAUDE.md`
defines. It runs when you ask for a rebase and never pushes.

## Prerequisites

- git 2.36 or newer.
- Python 3.9 or newer on a POSIX host, for the recovery helper.
- A remote carrying trunk; selection follows
  [the skill's inspection phase](skills/rebase/SKILL.md).

The helper keeps a backup branch and any saved edits, including their staging.
Conflicts remain available for a decision. Runtime depends on the commits
replayed and the project's quality checks, which run once after resolution.
