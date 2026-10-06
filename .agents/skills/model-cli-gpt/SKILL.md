---
name: model-cli-gpt
description: >-
  Use when invoking OpenAI GPT directly through the same Codex CLI or agent
  fallback used by the codex skill.
disable-model-invocation: true
allowed-tools: ["Bash"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>] [mode:plan]"
  source: "plugins/model-cli/skills/gpt/SKILL.md"
---

# GPT CLI Skill

Read the `model-cli-codex` skill and follow it with `$ARGUMENTS`, passing every
trigger through.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
