# action

Convert tickets to branches in isolated worktrees. Uses team branch
conventions, lands gated commits, and supports parallel tickets.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install action@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add action@skills
```

Claude Code uses a leading slash (`/action:…`). Codex omits it (`action:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/action:worktree [<ticket>...]` | `action:worktree [<ticket>...]` | One branch + worktree for one or more tickets: resolve read-only, name by convention, implement, land gated commits; push or PR only on request |
| `/action:worktrees [<ticket>...]` | `action:worktrees [<ticket>...]` | Discover and group several tickets, then fan out one worktree per unit — parallel subagents where the host supports them, sequential otherwise |

One ticket (or related set) → `worktree`. Independent tickets → `worktrees`.
(Use a review-response skill to land findings on the current branch; this plugin
creates new branches).

Flag axes:
- Placement: `--local` (default) creates a sibling worktree. `--temp` uses
  the host's temp-worktree mechanism.
- Exit: By default, commits locally. Optionally use `--push`, `--pr`, or
  `--setup-only`.

Additional flags: `/action:worktree` accepts `--branch=<name>`.
`/action:worktrees` accepts `--groups="a b; c"` and `--sequential`.

## Workflow

1. Awareness: Read conventions to discover formatting, linting, testing, and CI rules.
2. Resolution: Detect tracker, fetch ticket details read-only.
3. Naming: Follow precedence (explicit ask > conventions > tracker default > repo norms).
4. Plan: Confirm details before mutation.
5. Worktree: Idempotent setup (resumes existing, halts on collision).
6. Implement: Code and commit strictly inside the worktree, running gates.
7. Exit: Stop locally, push, PR, or setup-only.

Multi-ticket branches share a theme slug; ticket IDs ride in commits/PRs for linking.

## Zero Ticket Write-Back

Neither skill writes to a tracker. Links form server-side from branch and PR names.

## Shared References

Both commands share runtime procedures:
- `ticket-detection.md`: Tracker detection, branch naming, linking.
- `worktree-setup.md`: Worktree and branch setup, exit axis, teardown.
- `implement-and-commit.md`: Per-unit implement, gate, and commit procedure.
- `prose-rules.md`: Writing rules for reports, commits, and PR text.
- `verification-gates.md`: Quality-gate and CI discovery.

## Verification Discovery

Reads conventions (`AGENTS.md`) and CI configs to run necessary local checks.
Defers CI-covered work to `gh pr checks --watch` when pushing.

## Prerequisites

- git: Required for `git worktree`.
- gh (optional): For GitHub integration.
- Tracker MCP server (optional): For tools like Linear.
