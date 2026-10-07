---
name: model-cli-agy
description: >-
  Use when delegating to Google Gemini or Antigravity for a Gemini second
  opinion; runs write-enabled, no sandbox, unless mode:plan.
allowed-tools: ["Bash"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>] [mode:plan]"
  source: "plugins/model-cli/skills/agy/SKILL.md"
---

# Antigravity (agy) CLI Skill

Run a prompt through the Antigravity CLI (`agy`), falling back to the `agent`
CLI with a Gemini model. Follow `references/dispatch.md` for triggers,
running a tier, failure handling, and the report. Write the report per
`references/prose-rules.md`.

## Step 1: Detect CLIs

```console
$ command -v agy
```

```console
$ command -v agent
```

Skip tiers whose binary is missing. If neither is found, report both CLIs
unavailable and stop.

## Step 2: Run the tiers in order

`agy -p` consumes the next argument as the prompt, so `-p` comes after every
other flag and `"$prompt"` follows it directly.

Normal runs are write-enabled. `mode:plan` runs are read-only: `agy --mode
plan` and `agent --mode plan` are the CLIs' own plan modes, and the plan
commands omit the permission-skipping flags.

1. Normal: `agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions -p`
   Plan: `agy --model "Gemini 3.1 Pro (High)" --mode plan -p`
2. Normal: `agent -p -f --model gemini-3.1-pro --`
   Plan: `agent -p --mode plan --model gemini-3.1-pro --`
3. Normal: `agy --model "Gemini 3.8 Flash (High)" --dangerously-skip-permissions -p`
   Plan: `agy --model "Gemini 3.8 Flash (High)" --mode plan -p`

Tier 3 is the lesser fallback: when it runs, say the Pro tiers failed. If
tier 1 crashed on `agy`, skip tier 3.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
