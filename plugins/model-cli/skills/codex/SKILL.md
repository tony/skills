---
name: codex
description: "Use when asked to use Codex, GPT, OpenAI's model, or the Codex CLI to delegate a task; falls back to agent. Not for messaging a Codex session."
user-invocable: true
allowed-tools: ["Bash"]
argument-hint: <prompt> [timeout:<seconds>] [mode:plan]
---

# Codex CLI Skill

Run a prompt through the Codex CLI (OpenAI GPT), falling back to the `agent`
CLI with a GPT model. Follow `../../references/dispatch.md` for triggers,
running a tier, failure handling, and the report.

## Step 1: Detect CLIs

```console
$ command -v codex
```

```console
$ command -v agent
```

Skip tiers whose binary is missing. If neither is found, report both CLIs
unavailable and stop.

## Step 2: Run the tiers in order

Normal runs are write-enabled. `mode:plan` runs are read-only: `codex exec
--sandbox read-only` is Codex's read-only sandbox, and `agent --mode plan` is
Cursor's read-only plan mode.

1. Normal: `codex exec --yolo --skip-git-repo-check -c model_reasoning_effort=medium --`
   Plan: `codex exec --sandbox read-only --skip-git-repo-check -c model_reasoning_effort=medium --`
2. Normal: `agent -p -f --model gpt-5.4-high --`
   Plan: `agent -p --mode plan --model gpt-5.4-high --`
3. Normal: `agent -p -f --model gpt-5.4-mini-medium --`
   Plan: `agent -p --mode plan --model gpt-5.4-mini-medium --`

Tier 3 is the lesser fallback: when it runs, say the larger model failed. If
tier 2 crashed on `agent`, skip tier 3.
