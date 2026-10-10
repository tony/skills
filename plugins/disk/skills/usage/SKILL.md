---
name: usage
description: Survey disk usage across every filesystem layer and classify what is reclaimable, without deleting anything
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion
argument-hint: "[path or filesystem to focus on]"
disable-model-invocation: true
---

# Usage

Survey this machine's disk usage and report where the space went.

Scope: $ARGUMENTS — when empty, survey every mounted filesystem.

A named path limits the walk to that subtree; measure the filesystem
holding it with `df`. Leave other layers out unless the user asks about
the host. A category such as "build caches" limits the findings to that
category: inspect candidate locations from project configuration or
available tools, not unrelated system directories or host drives. If no
candidate can be read, use the blocked shape and ask for a readable path.
Do not assume an unread directory contains the category.

This command is read-only. Do not delete, move, or modify anything, and
do not write compressed files (measuring with `-c` to stdout is fine);
never halt a virtual machine or WSL guest. When run
directly rather than through the `disk` skill, end a sectioned report by
offering `/disk:reclaim`.

Obey the non-negotiables in `../disk/SKILL.md`, including when this
skill is invoked directly.

## Establish the layer structure

Run `df -h` and identify every distinct filesystem with its used and
available space. Determine which of them is the binding constraint —
the one closest to full, because that governs which findings matter.

Read `../../references/virtual-disks.md` only when a filesystem is a
virtual disk or the path sits on one (a WSL `/mnt` drive, a VM image).

For an in-scope virtual disk, compare its backing file's apparent size
with the guest's used space. Report their difference as an apparent gap,
not recoverable host space: sparse allocation and disk metadata differ.
Host recovery needs host-side allocation measurements before and after
compaction, as described in `../../references/virtual-disks.md`.

Check whether the guest issues TRIM and report it as a guest setting.

## Measure

Survey each filesystem separately with the script. It stays on one
filesystem, sets the size floor at one percent of capacity (so a small
disk still produces findings and a large one is not drowned), counts
hardlinks once, never follows symlinks, and lists unreadable paths under
`errors`. It skips `/mnt` (listed under `skipped`) unless the path you
give is inside it, so survey a Windows drive only when the user names it. When the user
scopes the survey to a path, lower `--floor-pct` so caches of a few GiB
still appear.
Print the absolute path of `../../scripts/survey.py` once (it resolves
from this file's directory) and write it literally:

```console
$ python3 /abs/path/to/scripts/survey.py \
    --depth 3 \
    --time-limit 90 \
    <scoped-path-or-mount-point>
```

`largest` ranks the biggest directories below the path whatever the floor.
An unreadable path or an expired `--time-limit` sets `"complete": false`;
sizes are then lower bounds, so report them as "at least" and name the
reason the survey is incomplete. On a large or network-backed filesystem, survey
the user's likely heavy subpaths one at a time with `--depth 2`, and
name which ones were left unmeasured.

Sizes are allocated bytes, so they can differ from `du --apparent-size`.
When the script is unavailable, `dust -x` or `du -x` with an explicit
depth and the same floor is the fallback; without `-x` a walk from `/`
enters `/mnt/c` and mixes layers.

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

Read `../../references/output-contract.md` before writing the reply.
When any layer or path cannot be read, use the blocked shape in
`../../references/output-contract.md`: no `##` sections, and never
attribute unmeasured space to a path or say where the answer probably is.
Name the layer, not the sandbox, and use only the four tiers in the
catalog (regenerable, redundant, needs a decision, protected).

Attach a path to a layer only from a measurement in this run. Do not
characterize an unmeasured path.

Follow `../../references/output-contract.md`. Write it per
`../../references/prose-rules.md`.
