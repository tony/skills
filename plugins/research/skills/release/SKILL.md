---
name: release
description: "Pass every check fresh, release the exact report to its readers, record decisions taken on it, and export the run as a fixity-checked bag"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "AskUserQuestion"]
argument-hint: "[topic or run directory] [--to=<readers>] [--offline]"
user-invocable: true
disable-model-invocation: true
---


# /research:release

Hand a topic's report to the people who act on it, with a trail from each decision back to the exact report version and the sources it rested on.

Invoke /research:foray with `release` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
