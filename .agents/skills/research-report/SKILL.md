---
name: research-report
description: >-
  Write a topic's report: the answer and summary first, findings next, then
  method, exhibits, and sources
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob"]
metadata:
  argument-hint: "[topic or run directory] [--audience=private|internal|public]"
  source: "plugins/research/skills/report/SKILL.md"
---

# this skill

Read the `research-foray` skill and follow it, treating `report` as the first word of the arguments.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
