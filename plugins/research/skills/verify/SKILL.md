---
name: verify
description: "Re-check a topic's sources (vanished, moved, changed, misquoted), look for missed sources, and lint the report"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
argument-hint: "[topic or run directory] [--offline]"
user-invocable: true
disable-model-invocation: true
---


# /research:verify

Check that a topic's references still say what the report cites them for, that no source it should rest on is missing, and that the report reads cleanly.

Invoke /research:foray with `verify` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
