---
name: continue
description: "Pick up a research topic or assessment: carry sources into today's run, re-verify them, then fill gaps or expand scope"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
argument-hint: "[topic] [--fill | --expand=<scope>] [--resume] [--root=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /research:continue

Resume a topic where its last run stopped. `--fill` works only the open questions; `--expand=<scope>` widens the scope first; neither means continue with the open questions and the weakest findings.

Invoke /research:foray with `continue` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
