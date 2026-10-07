---
name: disk-usage
description: >-
  Survey disk usage across every filesystem layer and classify what is
  reclaimable, without deleting anything
disable-model-invocation: true
allowed-tools: "Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  argument-hint: "[path or filesystem to focus on]"
  source: "plugins/disk/skills/usage/SKILL.md"
---

Survey this machine's disk usage and report where the space went.

Scope: $ARGUMENTS — when empty, survey every mounted filesystem.

This command is read-only. Do not delete, move, compress, or modify
anything, and never halt a virtual machine or WSL guest. When run
directly rather than through the `disk` skill, end by offering
the `disk-reclaim` skill.

## Establish the layer structure

Read `references/virtual-disks.md` first.

Run `df -h` and identify every distinct filesystem with its used and
available space. Determine which of them is the binding constraint —
the one closest to full, because that governs which findings matter.

When a filesystem is a virtual disk, find its backing file on the host
and compare that file's apparent size against the used space reported
inside the guest. The gap is balloon: space recoverable by compaction
alone, without deleting anything. Report it as a distinct figure.

Check whether the guest issues TRIM, so the report can explain whether
balloon will keep re-accumulating.

## Measure

Survey each filesystem separately and stay on one filesystem: `dust -x`
with an explicit depth and minimum size, falling back to `du -x`. Without
`-x`, a walk from `/` enters `/mnt/c` and other mounts and mixes layers.

Set the size floor (minimum size) relative to the filesystem rather than using a
fixed value, so a small disk still produces findings and a large one is
not drowned in them. Around one percent of total capacity works.

Resolve symlinks before recording a size, so no directory is counted
under two paths.

## Classify

Assign every candidate above the size floor to a tier from
`references/candidate-catalog.md`.

For anything holding agent transcripts or session data, read
`references/agent-history.md`. Report what is protected and why;
propose nothing destructive here.

For candidates that look like duplicates, run the proof in
`references/redundancy-proofs.md` and record its outcome.

For directories of upstream clones kept for reading, read
`references/study-repos.md`.

## Output

When any layer or path cannot be read, use the blocked shape in
`references/output-contract.md`: no `##` sections, and never
attribute unmeasured space to a path or say where the answer probably is.
Name the layer, not the sandbox, and use only the four tiers in the
catalog (regenerable, redundant, stale-but-unique, protected).

Follow `references/output-contract.md`. Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
