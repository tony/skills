---
name: goal-planner-synthesize
description: >-
  Use when explicitly asked to combine or refresh earlier goals while
  preserving requirement lineage, current exclusions, and authorization
  holds.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "<earlier goals and new steering> [host, profile, output root, stdout-only or save-and-print]"
  source: "plugins/goal-planner/skills/synthesize/SKILL.md"
---

# Synthesize goals

Reconcile earlier goals with current steering and print the complete handoff
without activating or executing it. Arguments: `$ARGUMENTS`.

Read [the contract](references/contract.md)
and [output contract](references/output.md). Read other references only
when their step applies. `<planner>` is
`references/planner.py`, resolved from this skill's directory to an absolute
path written literally in every command.

## 1. Read the originals

Read full goals, specifications, corrections, project rules, and evidence;
follow [recovery](references/recovery.md) when needed. Resolve target
identities, provenance, coverage gaps, and present authority before combining.
Use only selected [profiles and bindings](references/profiles.md).

## 2. Reconcile requirements

Apply the contract's synthesis rules to every input requirement. Write sourced
dispositions under [prose rules](references/prose-rules.md), retaining
stable keys, exclusions, holds, and failed findings. Inspect relevant current
state and revalidate evidence only where required; preserve accepted unchanged
results and completed criteria in the contract.

## Orchestration Plan

Drafting and requested saving are authorized. For separately requested
preparation that changes project state:

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present scope, owned artifacts, checks, and authority under
[prose rules](references/prose-rules.md); wait for approval unless the
session already authorizes that plan. Exit plan mode before preparation.

## 3. Produce the revised contract

Write the revised contract under [prose rules](references/prose-rules.md).
Consult [safeguards](references/safeguards.md) for concrete risks or
selected requirements, and before naming another skill in the goal. Check
coverage and challenge unnecessary inherited guarantees without dropping real
obligations. Required independent review covers the exact revised contract;
unavailable review remains UNVERIFIED.

## 4. Render and hand off

Follow [rendering](references/rendering.md) for host limits, predecessor
inputs, immutable revisions, and verification. Reply under
[output contract](references/output.md) and
[prose rules](references/prose-rules.md), printing the whole payload and
every requirement's disposition. If the helper returns no payload, print the
authored draft and concrete error as incomplete. Stop before native activation,
replacement, or execution.

Before sending, check the exact `## Goal` and `## Handoff` headings, complete
fenced payload, whole-payload count line, and inherited requirement dispositions.
Keep handoff status to one short line, with saved identities and material gaps
in their prescribed places.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
