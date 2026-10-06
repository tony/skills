---
name: reclaim
description: Reclaim disk space through a proof-gated plan — clears regenerable caches, merges proved-redundant copies, and protects agent history
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion, TodoWrite
argument-hint: "[path or filesystem to focus on]"
user-invocable: true
disable-model-invocation: true
---


Reclaim disk space on this machine without losing anything the user
cannot get back.

Scope: $ARGUMENTS — when empty, consider every mounted filesystem.

## Before anything else

Read the non-negotiables in `../disk/SKILL.md` and obey them, including
when this skill is invoked directly.

## Survey and classify

Follow `../usage/SKILL.md` and reuse its survey when one already ran
this session. Do not shortcut it because this skill will execute: the
classification is what makes execution safe.

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

Never present compression as free. Follow
`../../references/agent-history.md`: propose native compression where the
tool has it, otherwise an age cutoff the user chooses.

Exit plan mode once approved.

## Execute

Work the approved plan in tier order, largest first within each tier.
Track progress with TodoWrite so a long run stays inspectable.

Merges run before the deletions that depend on them. After each merge,
re-run the path-set comparison with arguments reversed and confirm the
source now holds nothing unique. Only then may the source be removed.

Prefer a tool's own prune or archive command over `rm`. It understands
its own reference counting and leaves the store consistent.

Before any `rm`, resolve the path with `realpath`, print the exact
target, and check that no process holds it open (`lsof +D <path>` or
`fuser -v <path>`). Stop if the resolved path leaves the approved scope.

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
host-side compaction. Take the exact commands from
`../../references/virtual-disks.md`, one per block, with where each runs
and what it interrupts stated before it. Where that file cites no
command for the user's host, say so rather than writing one from memory.

Report host recovery as pending rather than achieved, and say plainly
which numbers are measured and which are projected.

Follow `../../references/output-contract.md`. Write it per `../../references/prose-rules.md`.
