---
name: model-cli-codex
description: >-
  Use when asked to use Codex, GPT, OpenAI, or the Codex CLI to delegate;
  write-enabled unless mode:plan. Not for messaging a Codex session.
allowed-tools: ["Bash", "Write"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>] [mode:plan]"
  source: "plugins/model-cli/skills/codex/SKILL.md"
---

# Codex CLI Skill

Run a prompt through the Codex CLI (OpenAI GPT), falling back to the `agent`
CLI with a GPT model. Follow `references/dispatch.md` for triggers,
running a tier, failure handling, and the report. Write the report per
`references/prose-rules.md`.

## Step 1: Detect CLIs

```console
$ command -v codex
```

```console
$ command -v agent
```

Skip tiers whose binary is missing. If neither is found, stop and give the
failed-run report from `references/dispatch.md`.

## Step 2: Run the tiers in order

Normal runs are write-enabled. Codex bypasses its sandbox, and
`--skip-git-repo-check` removes its repo guard. Cursor retains its configured
sandbox. `mode:plan` runs are read-only: `codex exec
--sandbox read-only` is Codex's read-only sandbox, and `agent --mode plan` is
Cursor's read-only plan mode.

1. Normal: `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -c model_reasoning_effort=medium --`
   Plan: `codex exec --sandbox read-only --skip-git-repo-check -c model_reasoning_effort=medium --`
2. Normal: `agent -p -f --model gpt-5.4-high --`
   Plan: `agent -p --mode plan --model gpt-5.4-high --`
3. Normal: `agent -p -f --model gpt-5.4-mini-medium --`
   Plan: `agent -p --mode plan --model gpt-5.4-mini-medium --`

Pass `--require-flag=` with `--dangerously-bypass-approvals-and-sandbox` (tier 1)
or `-f` (tiers 2-3) on a normal run, and `--sandbox` (tier 1) or `--mode`
(tiers 2-3) on a `mode:plan` run.

Tier 3 requests the smaller fallback model. Report earlier tier failures in
the dispatch report's failed-tier lines. If tier 2 failed with auth, credit,
crash, or unsupported-flag on `agent`, skip tier 3.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
