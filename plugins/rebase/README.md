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

## Workflow

1. **Detect Trunk**: Identify the remote trunk branch (the remote's default branch).
2. **Analyze**: Fetch latest, identify changed files, and predict conflict zones.
3. **Rebase**: Record the pre-rebase tip, then run `git rebase --autostash origin/<trunk>`. Branches with merge commits stop for your decision.
4. **Resolve**: Resolve conflicts file-by-file: mechanical ones directly, and ask you when the two sides change the same code in competing ways.
5. **Verify**: Confirm clean history, compare patches with `git range-diff`, and run the quality gates once.

## Quality Gates & Design

- Reads `AGENTS.md` / `CLAUDE.md` to discover required checks.
- Does not hardcode linters or test runners; works with whatever the project uses.

## Prerequisites

- **git** for standard operations.
- A remote named `origin` with a trunk branch (the remote's default branch).
