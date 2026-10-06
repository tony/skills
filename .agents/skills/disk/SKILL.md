---
name: disk
description: >-
  Use when disk space is low; find large directories, free space, decide if
  Claude sessions or npm cache are safe to remove, or shrink WSL.
allowed-tools: "Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  source: "plugins/disk/skills/disk/SKILL.md"
---

# Disk

Find what is consuming a machine's disk and reclaim it without losing
anything the user cannot get back.

## Non-negotiables

- **Never halt the environment.** `wsl --shutdown`, `wsl --terminate`, VM
  stop commands, and container-runtime restarts are the user's to run.
  Print the command, say what it interrupts, and stop. Approval to delete
  caches is not approval to terminate the environment.
- **Never delete on the strength of a name.** `*-backup-*`, `.old`, `.bak`,
  and `archive-*` say nothing about redundancy. Run the proof.
- **Agent history is protected.** Reclaim from it only through the owning
  tool's archival path, or by proving one copy redundant against another.
- **Report guest and host separately.** Space freed inside a virtual disk
  is not freed on the machine until the disk is compacted.
- **A blanket approval covers only the regenerable tier.** Stale-but-unique
  data is decided per directory.

## Route

Read the sibling file and follow it. Both siblings open with
`Scope: $ARGUMENTS`, which a file read never substitutes: the scope is
the path the user named, or every mounted filesystem when none.

- Survey, "where did my space go", or no request to delete: follow
  the `disk-usage` skill. It is read-only, and the router run does not end
  with an offer to reclaim.
- Free space, clean up, or shrink WSL: follow the `disk-usage` skill, then
  the `disk-reclaim` skill, which reuses that survey instead of repeating it.

## Orchestration plan

Enter plan mode before proposing anything destructive. In Claude Code call
`EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text and wait for
approval. the `disk-reclaim` skill defines the plan's contents.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
