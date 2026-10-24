---
name: print
description: "Use when explicitly asked to print or draft a goal with preserved scope, measurable acceptance, and optional numbered goal specifications."
argument-hint: "<outcome> [host, limit, profile, earlier documents, output root, stdout-only or save-and-print]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Write, Grep, Glob, AskUserQuestion, Task]
---

# Print a goal

Draft and print a complete handoff without activating or executing it.
Arguments: `$ARGUMENTS`.

Read [the contract](../../references/contract.md),
[rendering](../../references/rendering.md), and
[output contract](../../references/output.md).

`<planner>` is `../../scripts/planner.py`, resolved from this skill's directory
to an absolute path written literally in every command.

## 1. Resolve the request

Resolve outcome, target, delivery host, output mode, authorization, and holds
from the request, project instructions, and supplied goals. Use only explicitly
selected [profiles and bindings](../../references/profiles.md). Follow
[recovery](../../references/recovery.md) when requested, needed, or selected by
that profile. Inspect current evidence only as needed for the contract.

Infer ordinary choices; ask only about missing decisions that materially
affect scope, authority, conflicting requirements, or a required companion.
Apply the contract's reconciliation and coverage rules to recovered material.

## Orchestration Plan

Drafting and requested saving are authorized. For separately requested
preparation that changes project state:

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present scope, owned artifacts, checks, and authority under
[prose rules](../../references/prose-rules.md); wait for approval unless the
session already authorizes that plan. Exit plan mode before preparation.

## 2. Draft and review

Write the complete contract under [prose rules](../../references/prose-rules.md).
Select applicable [safeguards](../../references/safeguards.md), then review
coverage against the originals. Arrange independent review when required;
preserve failures and repair gaps without inventing blockers.

## 3. Render, verify, and print

Follow [rendering](../../references/rendering.md) for host limits, helper input,
revision allocation, and verification. Answer under
[output contract](../../references/output.md) and
[prose rules](../../references/prose-rules.md), printing the whole exact payload
even when saved or incomplete. If the helper returns no payload, print the
authored draft and concrete error without claiming readiness. Stop at handoff;
never call native goal creation/update tools to test or activate it.
