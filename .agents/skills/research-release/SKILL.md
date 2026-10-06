---
name: research-release
description: >-
  Pass every check fresh, release the exact report to its readers, record
  decisions taken on it, and export the run as a fixity-checked bag
disable-model-invocation: true
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "AskUserQuestion"]
metadata:
  argument-hint: "[topic or run directory] [--to=<readers>] [--offline]"
  source: "plugins/research/skills/release/SKILL.md"
---

# this skill

Hand a topic's report to the people who act on it, with a trail from each decision back to the exact report version and the sources it rested on.

Invoke the `research-foray` skill with `release` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
