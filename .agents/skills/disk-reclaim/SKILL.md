---
name: disk-reclaim
description: >-
  Reclaim disk space through a proof-gated plan — clears regenerable caches,
  merges proved-redundant copies, and protects agent history
disable-model-invocation: true
allowed-tools: "Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  argument-hint: "[path or filesystem to focus on]"
  source: "plugins/disk/skills/reclaim/SKILL.md"
---

# Reclaim

Reclaim disk space on this machine without losing anything the user
cannot get back.

Scope: $ARGUMENTS — when empty, consider every mounted filesystem.

## Before anything else

Read the non-negotiables in the `disk` skill and obey them, including
when this skill is invoked directly.

## Survey and classify

Follow the `disk-usage` skill and reuse its survey when one already ran
this session. Do not shortcut it because this skill will execute: the
classification is what makes execution safe.

Carry forward, for every candidate: its tier, its size, the layer it
sits on, and for anything in the redundant tier, the proof outcome.

## Plan

Write the plan per `references/prose-rules.md`.

Enter plan mode before the first edit. In Claude Code call
`EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text.

Present the plan and wait for explicit approval before touching anything.

The plan states:

- What will be reclaimed per tier, with the proof that made each safe
- Expected recovery, attributed to the layer it lands on
- What the agent will run, separated from what only the user can run
- What is being left alone, and why

Group approvals by tier. Regenerable caches take one blanket approval.
Redundant copies are listed individually with their proof outcome.
Data without a proved replacement is decided per directory — a blanket approval
never covers this tier. Protected history appears as an inventory, or
as a verified native-archival proposal with its access tradeoff stated.

Follow `references/agent-history.md`; unverified archival support
halts that tier, rather than becoming an in-place compression proposal.

Exit plan mode once approved.

## Execute

Work the approved plan in tier order, largest first within each tier.
Track progress with TodoWrite so a long run stays inspectable.

Merges run before the deletions that depend on them. After each merge,
re-run both redundancy checks with the source as candidate and the
destination as keeper. Only a complete content proof permits removal.

Prefer a tool's own prune or archive command over `rm`. It understands
its own reference counting and leaves the store consistent.

Before any `rm`, run the guard. It resolves the path with `realpath`,
refuses a target outside the approved scope, overlapping a keeper, or
crossing a mount point, and
prints the target, its size, and its top-level entries. The guard checks scope and keepers, not tier: before each `rm`, say which approved tier and item the target belongs to, and delete nothing the approval did not name. Print the
absolute path of `references/guarded_rm.py` once (it resolves from this
file's directory) and write it literally:

```console
$ python3 /abs/path/to/scripts/guarded_rm.py \
    --scope <approved-scope> \
    --keeper <keeper> \
    <target>
```

Exit 2 means stop. On exit 0, run the same guard command with `--delete`
added; it checks visible open handles synchronously with `lsof` before
removal. Missing tools, warnings, timeouts, or open handles refuse deletion.
`fuser` cannot clear a warned scan: it can silently miss inaccessible
processes. This preflight is not a lock against new opens or mount changes.
Do not run a separate probe alongside
deletion or bypass the guard after refusal, including in commands offered
to the user. Narrow a large target when
inspection cannot complete. Pass `--keeper` once per redundant-tier keeper.

Stop and report rather than improvising when a proof fails, a candidate
turns out to hold unique data, or a repository has unpushed work. A
surprise is a signal the classification was wrong, not an obstacle to
route around.

## Verify

After each tier, re-read free space on the affected layer and report the
measured delta rather than the predicted one. A guarded deletion reports
its own before/after delta; retain it as that operation's observation.
When measured and predicted disagree, check resolved paths and measurement
layers before continuing. Use the completion template in
`references/output-contract.md`; report the cause as unchecked unless
an investigation establishes it.

## Hand off

Finish with `## Only you can run this`, the last section and omitted
when empty, holding the steps only the user can run: the in-guest
`sudo fstrim -av`, the guest shutdown, and any host-side compaction. Print
them only when an apparent size gap is measured or the user asked about
host space; otherwise write the one sentence the output contract gives,
with no commands. Take the exact commands from
`references/virtual-disks.md`, one per block, with where each runs
and what it interrupts stated before it. Where that file cites no
command for the user's host, say so rather than writing one from memory.

Report host recovery as pending rather than achieved, and say plainly
which numbers are measured and which are projected.

Follow `references/output-contract.md`. Write it per
`references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
