---
name: research-status
description: >-
  List research topics and assessments: latest run, source states, open
  questions, and the next action for each
disable-model-invocation: true
allowed-tools: ["Bash", "Read"]
metadata:
  argument-hint: "[--namespace=<ns>] [--root=<dir>]"
  source: "plugins/research/skills/status/SKILL.md"
---

# this skill

Read the `research-foray` skill and follow it, treating `status` as the first word of the arguments.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
