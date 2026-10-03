---
name: report
description: "Write a topic's report: the answer and summary first, findings next, then method, exhibits, and sources"
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob"]
argument-hint: "[topic or run directory] [--audience=private|internal|public]"
user-invocable: true
disable-model-invocation: true
---


# /research:report

Write or rewrite `report.md` for a topic's latest run, per the report standard, and ship it only when it passes the lint and the leak scan.

Invoke /research:foray with `report` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS
