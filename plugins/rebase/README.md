# rebase

Automated rebase onto trunk with conflict prediction, resolution, and quality gate verification.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install rebase@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add rebase@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/rebase` | `rebase` | Rebase current branch onto trunk, resolve conflicts, verify quality gates |

## Workflow

1. **Detect Trunk**: Identify the remote trunk branch (`main` or `master`).
2. **Analyze**: Fetch latest, identify changed files, and predict conflict zones.
3. **Rebase**: Run `git pull --rebase origin <trunk> --autostash`.
4. **Resolve**: Resolve conflicts file-by-file, preserving both sides' intent.
5. **Verify**: Confirm clean history and run full quality gates.

## Quality Gates & Design

- **Dynamic Discovery**: Reads `AGENTS.md` / `CLAUDE.md` to discover required checks.
- **Language-Agnostic**: Does not hardcode linters or test runners; works with whatever the project uses.

## Prerequisites

- **git** for standard operations.
- A remote named `origin` with a trunk branch (`main` or `master`).
