---
name: assess
description: "Assess a decision against stated criteria: sourced ratings per criterion and a verdict, kept in a dated topic folder"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
argument-hint: "[decision or question] [--root=<dir>] [--resume] [--audience=private|internal|public]"
user-invocable: true
disable-model-invocation: true
---


# /research:assess

Answer a decision question against criteria fixed before the evidence: rate each criterion from captured sources, then reach the verdict those ratings support.

Invoke /research:foray with `assess` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
