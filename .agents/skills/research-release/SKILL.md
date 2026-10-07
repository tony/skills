---
name: research-release
description: >-
  Pass every check fresh, release the exact report to its readers, record
  decisions taken on it, and export the run as a fixity-checked bag
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[topic or run directory] [--to=<readers>] [--offline]"
  source: "plugins/research/skills/release/SKILL.md"
---

# this skill

Read the `research-foray` skill and follow it, treating `release` as the first word of the arguments.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
