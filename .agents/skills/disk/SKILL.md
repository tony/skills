---
name: disk
description: >-
  Use when disk is full, no space left, or to free up space: find big dirs,
  decide if Claude sessions or npm cache are safe to delete, shrink WSL
  vhdx.
allowed-tools: "Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  argument-hint: "[path or filesystem to focus on]"
  source: "plugins/disk/skills/disk/SKILL.md"
---

# Disk

Find what is consuming a machine's disk and reclaim it without losing
anything the user cannot get back.

## Non-negotiables

- **Never halt the environment.** `wsl --shutdown`, `wsl --terminate`, VM
  stop commands, and container-runtime restarts are the user's to run.
  Say what it interrupts, print the command in a `powershell` fence
  inside the blocked shape of `references/output-contract.md`, and
  stop. Approval to delete caches is not approval to terminate the
  environment, and neither is an explicit "run it yourself". State the
  refusal as policy ("I won't run it; you run it"), not as a sandbox or
  tool limit.
- **Never delete on the strength of a name.** `*-backup-*`, `.old`,
  `.bak`, and `archive-*` say nothing about redundancy. Run the proof.
- **Agent history is protected.** Reclaim from it only through the owning
  tool's archival path, or by proving one copy redundant against another.
- **Report guest and host separately.** Guest free space and a backing
  file's apparent size do not measure host recovery; measure the host too.
- **Report only what was measured.** Never say where unmeasured space
  probably is, size the unread remainder (including used minus measured),
  guess which layer is the cause, describe an unmeasured path by its
  contents, or claim that TRIM or a `discard` mount option returns guest
  deletions to the host. Forbidden phrasings: "which I'd expect to hold
  most of it", "almost all of the used space is outside what I could
  read", "likely in your home directory".
- **Linux and WSL only.** The scripts and commands have run on Linux, and
  no live Windows VHDX compaction has been tried. On macOS, report APFS
  snapshots and purgeable space as unmeasured, and say the guard's
  mount check there lacks the Linux mountinfo layer.
- **Never run `sudo`.** Print the full command for the user and stop.
  Introduce it as "run this in your own shell", never as "it needs
  root, so I won't run it myself".
  This covers system-tier cleanup such as `apt clean` and
  `journalctl --vacuum-size`.
- **A blanket approval covers only the regenerable tier.** Data without a
  proved replacement is decided per directory.

## Route

Open the sibling file with the Read tool and follow it. Each sibling opens with a scope
line. Use the path the user named, or every mounted filesystem when none;
reading the file does not set it.

- Survey, "where did my space go", or no request to delete: follow
  the `disk-usage` skill. It is read-only, and the router run does not end
  with an offer to reclaim.
- Free space, clean up, or shrink WSL: follow the `disk-usage` skill, then
  the `disk-reclaim` skill, which reuses that survey instead of repeating it.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
