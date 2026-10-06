---
name: gemini
description: "Use when invoking Google's Gemini directly through the Antigravity or agent fallback chain."
user-invocable: true
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
argument-hint: <prompt> [timeout:<seconds>]
---

# Gemini CLI Skill

Alias for `/model-cli:agy`. Invoke the Antigravity (agy) CLI skill with
`$ARGUMENTS`, passing every trigger through.
