---
name: disk-reclaim
description: >-
  Reclaim disk space through a proof-gated plan — clears regenerable caches,
  merges proved-redundant copies, and protects agent history
allowed-tools: "Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, TodoWrite"
metadata:
  argument-hint: "[path or filesystem to focus on]"
  source: "plugins/disk/skills/reclaim/SKILL.md"
---

Reclaim disk space on this machine without losing anything the user
cannot get back.

Scope: $ARGUMENTS — when empty, consider every mounted filesystem.

## Before anything else

**Never halt the environment.** `wsl --shutdown`, `wsl --terminate`, VM
stop commands, and container-runtime restarts are the user's to run.
They destroy unsaved work across every shell, editor, and background job
on the machine. Print the command, state what it interrupts, and stop.
Approval to delete caches is not approval to terminate the environment.

**Never delete on the strength of a name.** Run the proof.

**Agent history is protected.** Reclaim from it only through the owning
tool's own archival path, or by proving one copy redundant against
another.

## Survey and classify

Run the same analysis the `disk-usage` skill performs. Do not shortcut it
because this command will execute — the classification is what makes
execution safe.

Establish the layer structure first, per
`references/virtual-disks.md`, so no guest-side
figure is mistaken for space recovered on the host.

Assign every candidate to a tier from
`references/candidate-catalog.md`, classifying
where content is homogeneous rather than propagating a parent's tier.

Prove every apparent duplicate with the path-set comparison in
`references/redundancy-proofs.md`. A `diff`
reporting no differing files proves nothing on its own.

Treat transcripts and session stores per
`references/agent-history.md`, resolving each
tool's discovery glob and native compression support before proposing
anything.

Handle directories of upstream clones per
`references/study-repos.md`, checking each for
unpushed work before calling it a conversion candidate.

Carry forward, for every candidate: its tier, its size, the layer it
sits on, and for anything in the redundant tier, the proof outcome.

## Plan

Enter plan mode before proposing anything destructive. In Claude Code
call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or
`Shift+Tab`. Where plan mode is unavailable, present the plan as text
and wait for explicit approval before touching anything.

The plan states:

- What will be reclaimed per tier, with the proof that made each safe
- Expected recovery, attributed to the layer it lands on
- What the agent will run, separated from what only the user can run
- What is being left alone, and why

Group approvals by tier. Regenerable caches take one blanket approval.
Redundant copies are listed individually with their proof outcome.
Stale-but-unique data is decided per directory — a blanket approval
never covers this tier. Protected history appears as an inventory, or
as a compression proposal with its access tradeoff stated.

Never present compression as free. When a tool cannot read its own
compressed history, compression converts sessions from resumable to
archive-only. Offer an age cutoff so recent sessions stay live, and let
the user choose. When a tool *can* compress natively, propose enabling
that instead of compressing by hand.

Exit plan mode once approved.

## Execute

Work the approved plan in tier order, largest first within each tier.
Track progress with TodoWrite so a long run stays inspectable.

Merges run before the deletions that depend on them. After each merge,
re-run the path-set comparison with arguments reversed and confirm the
source now holds nothing unique. Only then may the source be removed.

Prefer a tool's own prune or archive command over `rm`. It understands
its own reference counting and leaves the store consistent.

Stop and report rather than improvising when a proof fails, a candidate
turns out to hold unique data, or a repository has unpushed work. A
surprise is a signal the classification was wrong, not an obstacle to
route around.

## Verify

After each tier, re-read free space on the affected layer and report the
measured delta rather than the predicted one. When they disagree,
investigate before continuing — the usual cause is a virtual disk that
has not been compacted, or a symlink that made one directory look like
two.

## Hand off

Finish with the steps only the user can run: the guest shutdown, and any
host-side compaction. Give exact commands, one per block, with their
consequences stated.

Report host recovery as pending rather than achieved, and say plainly
which numbers are measured and which are projected.

Follow `references/output-contract.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
