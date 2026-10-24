---
name: profile
description: "Use when explicitly asked to create or revise portable goal-planning defaults and separate machine bindings with approved preferences."
argument-hint: "<selected defaults or candidate sources> [profile path, bindings path, propose-only or save]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Write, Grep, Glob, AskUserQuestion]
---

# Configure a planning profile

Propose or persist explicitly selected defaults. Arguments: `$ARGUMENTS`.
Profiles do not activate goals, import old permissions, or update memories.

Read [profile rules](../../references/profiles.md) and
[output contract](../../references/output.md). Apply
[prose rules](../../references/prose-rules.md) to candidates, plans, profile
principles, and responses. `<planner>` is `../../scripts/planner.py`, resolved
from this skill's directory to an absolute path written literally in commands.

## 1. Gather selections

Read the current request and explicitly selected existing profile. Separate
portable principles, current project rules, and machine bindings. Use
[recovery](../../references/recovery.md) only when requested or needed to
propose sourced candidates. Classify provenance and retain contradictions;
history alone never authorizes promotion.

Keep one-off release authority, platform exceptions, model names, machine
thresholds, and private paths scoped unless the user explicitly selects an
appropriate default. No implicit profile discovery or memory edits. Propose-only
and stdout-only requests must not write temporary inputs or settings.

## 2. Present proposed values

Write the complete proposed values under
[prose rules](../../references/prose-rules.md). Distinguish already selected
values from candidates awaiting approval. Use the strict schemas in
[profile rules](../../references/profiles.md). The Documents root is a separate
binding; do not equate native and mounted folders or infer a personal path.

An explicit instruction to save named values approves those values. Preserve
existing session approval. Otherwise, await the user's selection before any
persistent change. Do not serialize unapproved candidates with `approved: true`.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present selected values, profile/binding destinations, whether an existing file
will be replaced, and validation under
[prose rules](../../references/prose-rules.md). Wait for user approval unless
the current session already authorizes that exact change. Exit plan mode before
persistence. A helper approval flag records approval; it cannot supply it.

## 3. Validate and persist approved values

Use the helper's `profile read` or `bindings read` before updating an existing
file. For approved writes use the corresponding `write --input - --path ...
--approved` with JSON stdin. Add `--replace` only for an approved update to
an existing same-kind settings file. Follow the full commands in
[profile rules](../../references/profiles.md).

Read back the written file through the same helper and compare approved values.
Do not claim success after a validation or write failure. No settings are
applied automatically: later workflows use only a selected profile/binding.

## 4. Report and transfer

Print the complete proposed or saved values and persistence result under
[output contract](../../references/output.md) and
[prose rules](../../references/prose-rules.md). Identify unresolved capabilities.
Transfer only approved preferences through the user's selected mechanism;
exclude raw history, credentials, and private machine paths. Resolve bindings
on the receiving machine. Stop before activating any goal or changing other
configuration.
