---
name: research-verify
description: >-
  Re-check a topic's sources (vanished, moved, changed, misquoted), look for
  missed sources, and lint the report
disable-model-invocation: true
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebSearch", "AskUserQuestion"]
metadata:
  argument-hint: "[topic or run directory] [--offline]"
  source: "plugins/research/skills/verify/SKILL.md"
---

# this skill

Invoke the `research-foray` skill with `verify` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
