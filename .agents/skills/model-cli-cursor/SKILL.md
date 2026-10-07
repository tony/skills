---
name: model-cli-cursor
description: >-
  Use when asked to use Cursor, Cursor's CLI, or the agent binary to
  delegate a prompt or task; no fallback is available.
allowed-tools: ["Bash"]
metadata:
  argument-hint: "<prompt> [timeout:<seconds>] [mode:plan]"
  source: "plugins/model-cli/skills/cursor/SKILL.md"
---

# Cursor Agent CLI Skill

Run a prompt through Cursor's `agent` CLI. There is no fallback tier. Follow
`references/dispatch.md` for triggers, running a tier, failure handling,
and the report. Write the report per
`references/prose-rules.md`.

## Step 1: Detect the CLI

```console
$ command -v agent
```

If `agent` is not found, report it unavailable and stop.

## Step 2: Run the tier

Normal runs are write-enabled. `mode:plan` runs use `agent --mode plan`,
Cursor's read-only plan mode.

1. Normal: `agent -p -f --`
   Plan: `agent -p --mode plan --`

Failure of this tier, including credit exhaustion, ends the run: report it. Do not suggest or
run another vendor's CLI.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
