---
name: usage
description: Survey disk usage across every filesystem layer and classify what is reclaimable, without deleting anything
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite
argument-hint: "[path or filesystem to focus on]"
user-invocable: true
disable-model-invocation: true
---


Survey this machine's disk usage and report where the space went.

Scope: $ARGUMENTS — when empty, survey every mounted filesystem.

This command is read-only. Do not delete, move, compress, or modify
anything, and never halt a virtual machine or WSL guest. When run
directly rather than through the `disk` skill, end by offering
`/disk:reclaim`.

## Establish the layer structure

Read `../../references/virtual-disks.md` first.

Run `df -h` and identify every distinct filesystem with its used and
available space. Determine which of them is the binding constraint —
the one closest to full, because that governs which findings matter.

When a filesystem is a virtual disk, find its backing file on the host
and compare that file's allocated size against the used space reported
inside the guest. The gap is balloon: space recoverable by compaction
alone, without deleting anything. Report it as a distinct figure.

Check whether the guest issues TRIM, so the report can explain whether
balloon will keep re-accumulating.

## Measure

Survey each filesystem separately. Prefer `dust` with an explicit depth
and minimum size, falling back to `du` when unavailable.

Set the size floor (minimum size) relative to the filesystem rather than using a
fixed value, so a small disk still produces findings and a large one is
not drowned in them. Around one percent of total capacity works.

Resolve symlinks before recording a size, so no directory is counted
under two paths.

## Classify

Assign every candidate above the size floor to a tier from
`../../references/candidate-catalog.md`.

For anything holding agent transcripts or session data, read
`../../references/agent-history.md`. Report what is protected and why;
propose nothing destructive here.

For candidates that look like duplicates, run the proof in
`../../references/redundancy-proofs.md` and record its outcome.

For directories of upstream clones kept for reading, read
`../../references/study-repos.md`.

## Output

Follow `../../references/output-contract.md`. Write it per `../../references/prose-rules.md`.
