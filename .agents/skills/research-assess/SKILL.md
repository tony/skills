---
name: research-assess
description: >-
  Assess a decision against stated criteria: sourced ratings per criterion
  and a verdict, kept in a dated topic folder
disable-model-invocation: true
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
metadata:
  argument-hint: "[decision or question] [--root=<dir>] [--resume] [--audience=private|internal|public]"
  source: "plugins/research/skills/assess/SKILL.md"
---

# this skill

Answer a decision question against criteria fixed before the evidence: rate each criterion from captured sources, then reach the verdict those ratings support.

Invoke the `research-foray` skill with `assess` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
