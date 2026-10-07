---
name: disk
description: "Use when disk is full, out of space, or no space left: find large dirs, decide if Claude sessions or npm cache are safe to remove, shrink WSL vhdx."
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite
argument-hint: "[path or filesystem to focus on]"
---

# Disk

Find what is consuming a machine's disk and reclaim it without losing
anything the user cannot get back.

## Non-negotiables

- **Never halt the environment.** `wsl --shutdown`, `wsl --terminate`, VM
  stop commands, and container-runtime restarts are the user's to run.
  Print the command, say what it interrupts, and stop. Approval to delete
  caches is not approval to terminate the environment, and neither is an
  explicit "run it yourself". State the refusal as policy ("I won't run
  it; you run it"), not as a sandbox or tool limit.
- **Never delete on the strength of a name.** `*-backup-*`, `.old`, `.bak`,
  and `archive-*` say nothing about redundancy. Run the proof.
- **Agent history is protected.** Reclaim from it only through the owning
  tool's archival path, or by proving one copy redundant against another.
- **Report guest and host separately.** Space freed inside a virtual disk
  is not freed on the machine until the disk is compacted.
- **Never run `sudo`.** Print the full command for the user and stop.
- **A blanket approval covers only the regenerable tier.** Stale-but-unique
  data is decided per directory.

## Route

Read the sibling file and follow it. Each sibling opens with a scope line. Use the path the user named, or
every mounted filesystem when none; reading the file does not set it.

- Survey, "where did my space go", or no request to delete: follow
  `../usage/SKILL.md`. It is read-only, and the router run does not end
  with an offer to reclaim.
- Free space, clean up, or shrink WSL: follow `../usage/SKILL.md`, then
  `../reclaim/SKILL.md`, which reuses that survey instead of repeating it.

## Orchestration plan

Enter plan mode before proposing anything destructive. In Claude Code call
`EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text and wait for
approval. `../reclaim/SKILL.md` defines the plan's contents.
