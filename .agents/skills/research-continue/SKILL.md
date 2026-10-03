---
name: research-continue
description: >-
  Pick up a research topic or assessment: carry sources into today's run,
  re-verify them, then fill gaps or expand scope
disable-model-invocation: true
allowed-tools: ["Skill", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "AskUserQuestion"]
metadata:
  argument-hint: "[topic] [--fill | --expand=<scope>] [--resume] [--root=<dir>]"
  source: "plugins/research/skills/continue/SKILL.md"
---

# this skill

Resume a topic where its last run stopped. `--fill` works only the open questions; `--expand=<scope>` widens the scope first; neither means continue with the open questions and the weakest findings.

Invoke the `research-foray` skill with `continue` followed by the user arguments, and follow it.

User arguments: $ARGUMENTS


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
