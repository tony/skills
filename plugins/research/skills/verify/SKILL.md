---
name: verify
description: "Re-check a topic's sources (vanished, moved, changed, misquoted), look for missed sources, and lint the report"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
argument-hint: "[topic or run directory] [--offline]"
user-invocable: true
disable-model-invocation: true
---


# /research:verify

Invoke /research:foray with `verify` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
