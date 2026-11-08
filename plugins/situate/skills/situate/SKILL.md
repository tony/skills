---
name: situate
description: "Use when asked to situate yourself: sweep a branch, its tickets, CI checks, and conventions layer by layer, read-only."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[<pr-number|url>] [--with-agentgrep [terms]]"
---


# Situate

Answer one question: what is going on here, right now, and what would
someone picking this up need to know before touching anything.

Read `../../references/situation-sweep.md` first, and
`../../references/prior-conversations.md` before using
`--with-agentgrep`.

User arguments: $ARGUMENTS

## Procedure

### 1. Fix the scope

Default scope is the current branch measured against trunk, plus its
pull request if one is open.

A positional pull request number or URL switches the subject to that
pull request and its head branch. Read it through `gh`; do not check it
out. The sweep reference's pull-request-as-subject section gives the
commands.

The full sweep runs one script, several `git` and `gh` calls, and reads
the diff; `/situate:what` is the cheap alternative.

### 2. Sweep the layers

Work through the five repository layers in the order the sweep
reference sets out: position, change, pull request, tickets,
conventions. Gather all of them before writing anything; a ticket's
acceptance criteria reframe the diff that implements them.

### 3. Search prior conversations

Only with `--with-agentgrep`, when the user asks for it in words, or
when the request is to resume after a gap, under the prior-conversations
reference.
Derive the search terms from what the first five layers found unless
the user supplied them.

### 4. Report

Report in the shape in `../../references/report-shape.md`, per
`../../references/prose-rules.md`, with `## Prior work` only when the
prior-conversations layer ran. Then hand back; this command ends at
understanding.
