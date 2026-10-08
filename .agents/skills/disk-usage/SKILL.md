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

# Usage

Survey this machine's disk usage and report where the space went.

Scope: $ARGUMENTS — when empty, survey every mounted filesystem.

A named path limits the survey to the filesystem holding it: leave other
layers out instead of reporting them as unread, unless the user asks
about the host.

This command is read-only. Do not delete, move, or modify anything, and
do not write compressed files (measuring with `-c` to stdout is fine);
never halt a virtual machine or WSL guest. When run
directly rather than through the `disk` skill, end a sectioned report by
offering the `disk-reclaim` skill.

Obey the non-negotiables in the `disk` skill, including when this
skill is invoked directly.

## Establish the layer structure

Run `df -h` and identify every distinct filesystem with its used and
available space. Determine which of them is the binding constraint —
the one closest to full, because that governs which findings matter.

Read `references/virtual-disks.md` only when a filesystem is a
virtual disk or the path sits on one (a WSL `/mnt` drive, a VM image).

When a filesystem is a virtual disk, find its backing file on the host
and compare that file's apparent size against the used space reported
inside the guest. The gap is balloon: space recoverable by compaction
alone, without deleting anything. Report it as a distinct figure.

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
Print the absolute path of `references/survey.py` once (it resolves
from this file's directory) and write it literally:

```console
$ python3 /abs/path/to/scripts/survey.py \
    --depth 3 \
    --time-limit 90 \
    <mount-point>
```

The walk stops at `--time-limit` seconds and sets `"complete": false`;
every size is then a lower bound, so report it as "at least" and say the
survey was cut short. On a large or network-backed filesystem, survey
the user's likely heavy subpaths one at a time with `--depth 2`, and
name which ones were left unmeasured.

Sizes are allocated bytes, so they can differ from `du --apparent-size`.
When the script is unavailable, `dust -x` or `du -x` with an explicit
depth and the same floor is the fallback; without `-x` a walk from `/`
enters `/mnt/c` and mixes layers.

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

Read `references/output-contract.md` before writing the reply.
When any layer or path cannot be read, use the blocked shape in
`references/output-contract.md`: no `##` sections, and never
attribute unmeasured space to a path or say where the answer probably is.
Name the layer, not the sandbox, and use only the four tiers in the
catalog (regenerable, redundant, stale-but-unique, protected).

Attach a path to a layer only from a measurement in this run. Do not
characterize an unmeasured path.

Follow `references/output-contract.md`. Write it per
`references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
