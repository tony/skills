---
name: gpt
description: "Use when invoking OpenAI GPT directly through the same Codex CLI or agent fallback used by the codex skill."
user-invocable: true
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
argument-hint: <prompt> [timeout:<seconds>]
---

# GPT CLI Skill

Alias for `/model-cli:codex`. Invoke the Codex CLI skill with `$ARGUMENTS`,
passing every trigger through.
