# ticket

Manage work across trackers (Linear, Jira, GitHub, etc.) respecting native
object graphs. Drafts durable, invariant-focused tickets.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install ticket@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add ticket@skills
```

Claude Code uses a leading slash (`/ticket:…`). Codex omits it (`ticket:…`).

## Components

### `/ticket:draft`

Drafts new items across supported trackers. Resolves provider roles, reads
templates, gathers evidence, and presents before filing. Emits text to paste
if no backend exists.

### `/ticket:rebuild`

Rebuilds messy live items. Sorts body into keep/cut/relocate/demote/repair.
Relocates depth to linked documents. Updates only on approval.

## Content Rules

- **Past**: Include unrecoverable context (e.g., dead ends, conditions). Drop info visible in logs.
- **Present**: Avoid rotting references or unwanted backlinks.
- **Future**: Focus on invariants (failing tests). Skip checkboxes or measurement thresholds.

## Provider Object Graphs

Trackers use different native nouns. The plugin maps objects to canonical roles (e.g., Linear Project ≈ Jira Epic).
- See `references/hierarchy.md` for roles and collisions.
- See `references/providers/` for provider-specific hierarchies and capabilities.

## When to Use

- **`ticket`**: For non-GitHub trackers, non-issue objects (epics, projects), or rebuilding items.
- **`gh`**: For standard GitHub issues (`gh:create-issue`).
- **`pr`**: For branch pull request descriptions.
- **`lean`**: For shortening already-accurate text.

## Prerequisites

- **gh**: For GitHub.
- Works locally for other providers or falls back to text emission.
- Integrates with `pr` or `slop` plugins for mechanical checks, skipping gracefully if missing.
