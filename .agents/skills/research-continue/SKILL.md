---
name: research-continue
description: >-
  Pick up a research topic or assessment: carry sources into today's run,
  re-verify them, then fill gaps or expand scope
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebSearch", "AskUserQuestion"]
metadata:
  argument-hint: "[topic] [--fill | --expand=<scope>] [--resume] [--root=<dir>]"
  source: "plugins/research/skills/continue/SKILL.md"
---

# this skill

Read the `research-foray` skill and follow it, treating `continue` as the first word of the arguments.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
