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

## Tiers

Pick the tier and each model by the rules in `../../references/dispatch.md`,
using the list command, template, and commands below. Pass `<model>` as one
quoted argument; when the picker finds none, drop `--model <model>`. `agy -p`
consumes the next argument as the prompt, so `-p` comes after every other flag.

1. `agy`. List: `agy models` with `--emit label`. Template: `gemini-{v}-pro-high`.
   Normal: `agy --model <model> --dangerously-skip-permissions -p`
   Plan: `agy --model <model> --mode plan -p`
2. `agent`. List: `agent --list-models`. Template: `gemini-{v}-pro`.
   Normal: `agent -p -f --trust --model <model> --`
   Plan: `agent -p --mode plan --model <model> --`
3. `agy`. List: `agy models` with `--emit label`. Template: `gemini-{v}-flash-high`.
   Commands: tier 1's.
