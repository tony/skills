---
name: codex
description: "Use when asked to use Codex, GPT, OpenAI, or the Codex CLI to delegate; write-enabled unless mode:plan. Not for messaging a Codex session."
allowed-tools: ["Bash", "Write"]
argument-hint: <prompt> [timeout:<seconds>] [mode:plan]
---

# Codex CLI Skill

Run a prompt through the Codex CLI (OpenAI GPT), falling back to the `agent`
CLI with a GPT model. Follow `../../references/dispatch.md` for triggers,
running a tier, failure handling, and the report. Write the report per
`../../references/prose-rules.md`.

## Tiers

Pick the tier and each model by the rules in `../../references/dispatch.md`,
using the list command, template, and commands below. Pass `<model>` as one
quoted argument; when the picker finds none, drop `--model <model>`. Tier 1
passes no model, so Codex uses the user's configured one.

Codex refuses to run outside a Git repository, where the runner's state check
is also unavailable. Add `--skip-git-repo-check` to tier 1 only when the user
asks to run there, and report that the state check could not cover the run.

1. `codex`. Read the prompt from stdin: pass `--stdin` to the runner.
   Normal: `codex exec --dangerously-bypass-approvals-and-sandbox -`
   Plan: `codex exec --sandbox read-only -`
2. `agent`. List: `agent --list-models`. Template: `gpt-{v}-*high`, excluding `mini`.
   Normal: `agent -p -f --trust --model <model> --`
   Plan: `agent -p --mode plan --model <model> --`
3. `agent`. List: `agent --list-models`. Template: `gpt-{v}-mini-medium`.
   Commands: tier 2's.
