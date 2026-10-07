---
name: continue
description: "Pick up a research topic or assessment: carry sources into today's run, re-verify them, then fill gaps or expand scope"
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[topic] [--fill | --expand=<scope>] [--resume] [--root=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /research:continue

Read `../foray/SKILL.md` and follow it, treating `continue` as the first word of the arguments.

User arguments: $ARGUMENTS
