---
name: disk-usage
description: >-
  Survey disk usage across every filesystem layer and classify what is
  reclaimable, without deleting anything
allowed-tools: "Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  argument-hint: "[path or filesystem to focus on]"
  source: "plugins/disk/skills/usage/SKILL.md"
---

Survey this machine's disk usage and report where the space went.

Scope: $ARGUMENTS — when empty, survey every mounted filesystem.

This command is read-only. Do not delete, move, compress, or modify
anything. Do not halt a virtual machine or WSL guest under any
circumstance. Produce an analysis the user can act on, and end by
offering the `disk-reclaim` skill.

## Establish the layer structure

Read `references/virtual-disks.md` first.

Run `df -h` and identify every distinct filesystem with its used and
available space. Determine which of them is the binding constraint —
the one closest to full — because that governs which findings matter.

When a filesystem is a virtual disk, find its backing file on the host
and compare that file's allocated size against the used space reported
inside the guest. The gap is balloon: space recoverable by compaction
alone, without deleting anything. Report it as a distinct figure.

Check whether the guest issues TRIM, so the report can explain whether
balloon will keep re-accumulating.

## Measure

Survey each filesystem separately. Prefer `dust` with an explicit depth
and minimum size, falling back to `du` when unavailable.

Set the minimum size relative to the filesystem rather than using a
fixed value, so a small disk still produces findings and a large one is
not drowned in them. Around one percent of total capacity works.

Resolve symlinks before recording a size. Configuration directories
managed by a dotfiles repository routinely appear under two paths, and
counting both inflates the total while implying a duplicate that does
not exist.

## Classify

Assign every candidate to a tier from
`references/candidate-catalog.md`. Classify at
the level where content is homogeneous — a protected history root
frequently contains regenerable build artifacts, and those are
separable.

For anything holding agent transcripts or session data, read
`references/agent-history.md`. Identify each
tool's discovery glob, whether it maintains a state database, and
whether it supports compressing its own history natively. Report what
is protected and why; propose nothing destructive here.

For candidates that look like duplicates, run the path-set comparison
in `references/redundancy-proofs.md` and record
the outcome as redundant, mergeable, conflicted, or unique. A directory
named like a backup is not a backup until the proof says so — and a
`diff` reporting no differing files proves nothing on its own.

For directories of upstream clones kept for reading, read
`references/study-repos.md`. Report huge clones,
clones that are not shallow, and build artifacts as three separate
groups, and check each clone for unpushed work before calling it a
conversion candidate.

## Output

Follow `references/output-contract.md`.

Lead with the binding constraint in one line. An inventory of large
directories does not answer "where did my space go" when the real limit
is a different layer the user has not looked at.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
