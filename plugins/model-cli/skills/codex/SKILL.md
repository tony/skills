---
name: codex
description: "Use when asked to use Codex, GPT, OpenAI's model, or the Codex CLI to delegate a task; falls back to the GPT agent when needed."
user-invocable: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
argument-hint: <prompt> [timeout:<seconds>]
---

# Codex CLI Skill

Run a prompt through the Codex CLI (OpenAI GPT), falling back to the `agent`
CLI with a GPT model.

Follow `../../references/dispatch.md` for triggers, the timeout command, the
prompt file, running a tier, failure handling, and return. Stderr file prefix:
`codex`.

## Step 1: Detect CLI

```bash
command -v codex >/dev/null 2>&1 && echo "codex:available" || echo "codex:missing"
```

```bash
command -v agent >/dev/null 2>&1 && echo "agent:available" || echo "agent:missing"
```

If neither is found, report both CLIs unavailable and stop.

## Step 2: Run the tiers in order

1. `codex exec --yolo --skip-git-repo-check -c model_reasoning_effort=medium`
2. `agent -p -f --model gpt-5.4-high`
3. `agent -p -f --model gpt-5.4-mini` (lesser fallback)

Skip tiers whose binary is missing.
