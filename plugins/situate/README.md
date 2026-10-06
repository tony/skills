# situate

Gain situational awareness before modifying code. Scans branches, PRs,
tickets, and project conventions to orient the agent and verify the work
required.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install situate@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add situate@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/situate` | `situate` | Sweep current branch, PR, tickets, and conventions; report the situation. Defaults to current branch vs trunk. |
| `/situate:what` | `situate:what` | Five-line summary of what is going on, with numbered options for real choices. |
| `/situate:refocus` | `situate:refocus` | Re-derive the goal, sort commits against it, and identify drift and gaps. |

**Arguments:**
- `/situate`: 
  - `--pr <number|url>`: Target a PR without checking it out.
  - `--with-agentgrep [terms]`: Search local AI transcripts for
    unrecorded decisions.
- `/situate:what`: Accepts an optional subject (e.g., `/situate:what the
  test failure`).
- `/situate:refocus`: Accepts an optional goal.

## Layers

Gathers context in order, degrading gracefully if unavailable:
1. **Position**: Branch, trunk HEAD, ahead/behind, uncommitted work,
   stashes.
2. **Change**: Commits since merge-base, grouped by area.
3. **Pull request**: PR state, CI checks, unresolved review threads.
4. **Tickets**: Issue IDs found in commits, branch name, or PR body.
5. **Conventions**: `AGENTS.md` / `CLAUDE.md` rules and quality gates.
6. **Prior conversations**: Opt-in via `agentgrep`.

## Design Principles

- **Strictly Read-only**: No commits, edits, stashes, branch switches, or
  `git fetch` operations. Reports the environment exactly as it exists.
- **Prior Conversations (agentgrep)**: Off by default. Supplements
  unrecorded intent from local AI transcripts but prioritizes repository
  state when conflicts arise.
- **The Brief (`/situate:what`)**: Ruthlessly concise (5-line ceiling).
  Drops empty slots to save time. Relies on cheap local evidence first.
- **Goal and Drift (`/situate:refocus`)**: Re-derives goals organically
  rather than storing them. Categorizes commits into correct work,
  load-bearing detours, and genuine excursions using properly resolved
  bases.

## Shared References
- `references/situation-sweep.md`: The six layers, commands, and
  evidence discipline.
- `references/prior-conversations.md`: Transcript search rules and
  reconciliation.
- `references/brief.md`: Budget, ranking, and formatting for summaries.
- `references/goal-derivation.md`: Goal precedence, classification, and
  correctives.

## Prerequisites
- `git`
- `gh` CLI (optional, but needed for PRs/issues/threads)
- `uvx` (only required for `--with-agentgrep` to run
  [agentgrep](https://pypi.org/project/agentgrep/))
