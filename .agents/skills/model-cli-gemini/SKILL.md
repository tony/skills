---
name: model-cli-gemini
description: >-
  Use when invoking Google's Gemini directly through the Antigravity or
  agent fallback chain.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>]"
  source: "plugins/model-cli/skills/gemini/SKILL.md"
---

# Gemini CLI Skill

Alias for the `model-cli-agy` skill. Invoke the Antigravity (agy) CLI skill with
`$ARGUMENTS`, passing every trigger through.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
