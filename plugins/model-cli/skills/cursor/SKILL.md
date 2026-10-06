---
name: cursor
description: "Use when asked to use Cursor, Cursor's CLI, or the agent binary to delegate a prompt or task; no fallback is available."
user-invocable: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
argument-hint: <prompt> [timeout:<seconds>]
---

# Cursor Agent CLI Skill

Run a prompt through Cursor's `agent` CLI. There is no fallback tier.

Follow `../../references/dispatch.md` for triggers, the timeout command, the
prompt file, running a tier, failure handling, and return. Stderr file prefix:
`cursor`.

## Step 1: Detect CLI

```bash
command -v agent >/dev/null 2>&1 && echo "agent:available" || echo "agent:missing"
```

If `agent` is not found, report it unavailable and stop.

## Step 2: Run the tier

1. `agent -p -f`

Credit exhaustion has no next tier: report it and stop.
