# rebase

Automated rebase onto trunk with conflict prediction, resolution, and quality gate verification.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/ai-workflow-plugins
```

Install the plugin:

```console
/plugin install rebase@ai-workflow-plugins
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/ai-workflow-plugins
```

Install the plugin:

```console
codex plugin add rebase@ai-workflow-plugins
```

The skills below are written with Claude Code's leading slash. Codex uses
the same names without it, so `/rebase:…` there is `rebase:…`.

## Skills

| Skill | Description |
|---------|-------------|
| `/rebase` | Rebase current branch onto trunk, resolve conflicts, verify quality gates |

## 5-Phase Workflow

1. **Detect trunk** — Identify the remote trunk branch (`main` or `master`)
2. **Fetch and analyze** — Fetch latest, identify files changed on both sides, predict conflict zones
3. **Execute rebase** — Run `git pull --rebase origin <trunk> --autostash`
4. **Resolve conflicts** — If any conflicts arise, resolve them file-by-file preserving both sides' intent
5. **Verify** — Confirm clean history, run the project's full quality gate suite

## Quality Gate Discovery

The command reads AGENTS.md / CLAUDE.md to discover which quality checks the project requires. It does **not** hardcode any specific test runner or linter — it works with whatever the project uses.

## Prerequisites

- **git** — the rebase command uses standard git operations
- A remote named `origin` with a trunk branch (`main` or `master`)

## Language-Agnostic Design

Quality gate examples are provided for reference, but the command always defers to the project's own AGENTS.md / CLAUDE.md for the actual commands to run.
