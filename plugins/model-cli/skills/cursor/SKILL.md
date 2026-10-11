---
name: cursor
description: "Use when asked to use Cursor, Cursor's CLI, or the agent binary to delegate; write-enabled unless mode:plan; no fallback."
allowed-tools: ["Bash", "Write"]
argument-hint: <prompt> [timeout:<seconds>] [mode:plan]
---

# Cursor Agent CLI Skill

Run a prompt through Cursor's `agent` CLI. There is no fallback tier. Follow
`../../references/dispatch.md` for triggers, running a tier, failure handling,
and the report. Write the report per
`../../references/prose-rules.md`.

## Tier

One tier, `agent`, with no `--model`, so Cursor uses its default model.

1. Normal: `agent -p -f --trust --`
   Plan: `agent -p --mode plan --`
