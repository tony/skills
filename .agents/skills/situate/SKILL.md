---
name: situate
description: >-
  Gain situational awareness — read the branch, its diff, its PR, its
  tickets, and the project's own conventions, and report where the work
  stands
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[<pr-number|url>] [--with-agentgrep [terms]]"
  source: "plugins/situate/skills/situate/SKILL.md"
---

# Situate

Answer one question: what is going on here, right now, and what would
someone picking this up need to know before touching anything.

Read `references/situation-sweep.md` first; it
defines the six evidence layers, how each degrades, and the read-only
contract. Read
`references/prior-conversations.md` before using
`--with-agentgrep`.

User arguments: $ARGUMENTS

## Procedure

### 1. Fix the scope

Default scope is the current branch measured against trunk, plus its
pull request if one is open.

A positional pull request number or URL switches the subject to that
pull request and its head branch. Read it through `gh`; do not check it
out.

### 2. Sweep the layers

Work through the five repository layers in the order the sweep
reference sets out: position, change, pull request, tickets,
conventions. Gather all of them before writing anything; a ticket's
acceptance criteria reframe the diff that implements them.

### 3. Search prior conversations

Only with `--with-agentgrep`, under the prior-conversations reference.
Derive the search terms from what the first five layers found unless
the user supplied them.

### 4. Report

Report in the shape in `references/report-shape.md`, per
`references/prose-rules.md`, with `## Prior work` only when
`--with-agentgrep` ran. Then hand back; this command ends at
understanding.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
