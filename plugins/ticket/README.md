# ticket

Manage work across trackers (Linear, Jira, GitHub, and others),
respecting native object graphs. Drafts durable, invariant-focused
tickets.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install ticket --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install ticket@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add ticket@skills
```

Claude Code uses a leading slash (`/ticket:…`). Codex omits it
(`ticket:…`).

## Components

### `/ticket:draft`

Drafts new items across supported trackers. Resolves provider roles,
reads templates, gathers evidence, and presents before filing. Emits
text to paste if no backend exists. Scans the body for credentials,
local paths, and rotting references before any preview, and checks
the filed item reads back as written. Jira and Asana bodies are
converted by tested scripts; an Azure DevOps HTML field is print-only.

### `/ticket:rebuild`

Rebuilds messy live items. Sorts the body into keep, cut, relocate,
demote, and repair. Relocates depth to linked documents. Updates only on
approval, and checks the body, title, and inline images read back.

## Content Rules

`references/contract.md` holds the rules for what a body carries
(past, present, future) and how it is written.

## Provider Object Graphs

Trackers use different native nouns. The plugin maps objects to
canonical roles (for example, Linear Project is close to Jira Epic).

- `references/hierarchy.md` lists roles and collisions.
- `references/resolve.md` indexes the provider files under
  `references/providers/`.

## When to Use

- `ticket`: for any tracker, GitHub included, any object from a single
  issue to an epic or project, and for rebuilding items.
- `gh:create-issue`: a separate, narrower skill for a plain GitHub bug
  report. `ticket:draft` also files GitHub issues, with the security
  halt, duplicate search, scan, and readback.
- `pr`: for branch pull request descriptions.
- `lean`: for shortening already-accurate text.

## Filing and print-only

- Files when a backend is connected: GitHub (`gh`), GitLab (`glab`),
  Azure DevOps (`az`), Jira (`acli`, plain text), Linear, Asana, and
  Shortcut (MCP server), Trello (MCP or REST). Jira bodies are filed as
  plain text, so a body with a table or a nested list is printed
  instead.
- Prints the body to paste: any other tracker, and any provider above
  with no backend connected.

## Prerequisites

- `gh`: for GitHub. `glab`: for GitLab. `acli`: for Jira. `az` with the
  `azure-devops` extension: for Azure DevOps.
- Works locally for other providers or falls back to text emission.
