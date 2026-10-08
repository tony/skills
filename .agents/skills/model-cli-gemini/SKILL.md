---
name: model-cli-gemini
description: >-
  Use when invoking Google's Gemini directly through Antigravity or agent;
  writes unsandboxed unless mode:plan.
disable-model-invocation: true
allowed-tools: ["Bash"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>] [mode:plan]"
  source: "plugins/model-cli/skills/gemini/SKILL.md"
---

# Gemini CLI Skill

Read the `model-cli-agy` skill and follow it with `$ARGUMENTS`, passing every trigger
through.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
