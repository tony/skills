---
name: status
description: "List research topics and assessments: latest run, source states, open questions, and the next action for each"
allowed-tools: ["Skill", "Bash", "Read"]
argument-hint: "[--namespace=<ns>] [--root=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /research:status

Show where every topic stands and what to do next. Read-only.

Invoke /research:foray with `status` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
