---
name: model-cli-agy
description: >-
  Use when delegating to Google Gemini or Antigravity for a second opinion
  from Gemini, Google's model; falls back to the agent CLI.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>]"
  source: "plugins/model-cli/skills/agy/SKILL.md"
---

# Antigravity (agy) CLI Skill

Run a prompt through the Antigravity CLI (`agy`), falling back to the `agent`
CLI with `--model gemini-3.1-pro`.

Follow `references/dispatch.md` for triggers, the timeout command, the
prompt file, running a tier, failure handling, and return. Stderr file prefix:
`agy`.

## Step 1: Detect CLI

```bash
command -v agy >/dev/null 2>&1 && echo "agy:available" || echo "agy:missing"
```

```bash
command -v agent >/dev/null 2>&1 && echo "agent:available" || echo "agent:missing"
```

If neither is found, report both CLIs unavailable and stop.

## Step 2: Run the tiers in order

`agy`'s `-p`/`--print`/`--prompt` is a Go-style flag that consumes the **next argument** as the prompt, so the prompt must be the value of `-p` and `-p` must come **after** every other flag. Putting `-p` first (with the prompt as a trailing positional) makes agy swallow the following flag as the prompt and silently answer the wrong thing.

1. `agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions -p`
2. `agent -p -f --model gemini-3.1-pro`
3. `agy --model "Gemini 3.5 Flash (High)" --dangerously-skip-permissions -p` (only if `agy` is installed)

Skip tiers whose binary is missing. Tier 3 is the lesser fallback: when it
runs, say the Pro backends were exhausted.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
