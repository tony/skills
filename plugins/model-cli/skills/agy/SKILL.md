---
name: agy
description: "Use when delegating to Google Gemini or Antigravity for a Gemini second opinion; runs write-enabled unless mode:plan."
allowed-tools: ["Bash", "Write"]
argument-hint: <prompt> [timeout:<seconds>] [mode:plan]
---

# Antigravity (agy) CLI Skill

Run a prompt through the Antigravity CLI (`agy`), falling back to the `agent`
CLI with a Gemini model. Follow `../../references/dispatch.md` for triggers,
running a tier, failure handling, and the report. Write the report per
`../../references/prose-rules.md`.

## Step 1: Detect CLIs

```console
$ command -v agy
```

```console
$ command -v agent
```

Skip tiers whose binary is missing. If neither is found, stop and give the
failed-run report from `../../references/dispatch.md`.

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

Pass `--require-flag=` with `--dangerously-skip-permissions` (tiers 1, 3) or `-f`
(tier 2) on a normal run, and `--mode` on a `mode:plan` run.

Tier 3 requests the smaller fallback model. Report earlier tier failures in
the dispatch report's failed-tier lines. If tier 1 failed with auth, credit,
crash, or unsupported-flag on `agy`, skip tier 3.
