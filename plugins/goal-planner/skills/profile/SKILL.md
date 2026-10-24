---
name: profile
description: "Use when explicitly asked to create or revise portable goal-planning defaults and separate machine bindings with approved preferences."
argument-hint: "<selected defaults or candidate sources> [profile path, bindings path, propose-only or save]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Write, Grep, Glob, AskUserQuestion]
---

# Configure a planning profile

Propose or persist selected defaults without activating goals, importing old
permissions, or updating memories. Arguments: `$ARGUMENTS`.

Read [profile rules](../../references/profiles.md) and
[output contract](../../references/output.md). `<planner>` is
`../../scripts/planner.py`, resolved from this skill's directory to an absolute
path written literally in commands.

## 1. Gather selections

Read the request and selected existing profile; separate portable preferences,
project context, and machine bindings under the profile rules. Use
[recovery](../../references/recovery.md) when requested or needed for candidates.
Propose-only and stdout-only must not write temporary inputs or settings.

## 2. Present proposed values

Write complete proposed values under [prose rules](../../references/prose-rules.md)
using the profile schemas. Distinguish approved selections from candidates;
await selection only for values the session has not already approved.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present values, destinations, replacements, and validation under
[prose rules](../../references/prose-rules.md). Wait for approval unless the
session already authorizes that change. Exit plan mode before persistence.

## 3. Validate and persist approved values

Follow the helper commands and read-back checks in
[profile rules](../../references/profiles.md). Validation or write failure is
not success; approved settings apply only when later workflows select them.

## 4. Report and transfer

Report complete values, persistence, and unresolved capabilities under
[output contract](../../references/output.md) and
[prose rules](../../references/prose-rules.md). Follow profile transfer rules
only when requested. Stop before goal activation or other configuration changes.
