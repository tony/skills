---
name: research-report
description: >-
  Write a topic's report: the answer and summary first, findings next, then
  method, exhibits, and sources
disable-model-invocation: true
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob"]
metadata:
  argument-hint: "[topic or run directory] [--audience=private|internal|public]"
  source: "plugins/research/skills/report/SKILL.md"
---

# this skill

Write or rewrite `report.md` for a topic's latest run, per the report standard, and ship it only when it passes the lint and the leak scan.

Invoke the `research-foray` skill with `report` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
