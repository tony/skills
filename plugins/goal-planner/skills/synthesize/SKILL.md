---
name: synthesize
description: "Use when explicitly asked to combine or refresh earlier goals while preserving requirement lineage, current exclusions, and authorization holds."
argument-hint: "<earlier goals and new steering> [host, profile, output root, stdout-only or save-and-print]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Write, Grep, Glob, AskUserQuestion, Task]
---

# Synthesize goals

Reconcile complete earlier goals with current instructions and evidence, then
print the entire revised handoff. Arguments: `$ARGUMENTS`. Synthesis never
replaces an active native goal or begins the proposed work.

Read [the contract](../../references/contract.md),
[rendering](../../references/rendering.md), and
[output contract](../../references/output.md). Apply
[prose rules](../../references/prose-rules.md) to every authored draft,
disposition, plan, and response. `<planner>` is `../../scripts/planner.py`,
resolved from this skill's directory to an absolute path written literally
in every command.

## 1. Read the originals

Read full goals, specifications, corrections, and supplied evidence. Follow
[recovery](../../references/recovery.md) when history is needed. Do not infer
missing bodies from titles, summaries, or paste placeholders. Record source
and result coverage gaps. Classify direct human steering separately from
quoted, generated, or assistant-authored material.

Resolve target identities before combining. Namespace colliding requirement
keys from different targets. Keep current session authorization and explicit
holds separate from proposed future authority. A historical permission to
publish does not authorize publication here.

## 2. Reconcile requirements

Assign every input requirement a disposition: retained, revised, superseded,
deferred, excluded by explicit instruction, or unresolved. Write dispositions
under [prose rules](../../references/prose-rules.md), with the source of each
change. Preserve stable descriptive keys and failed findings. Integrate user
addenda as new steering; never silently change an old saved specification.

Current explicit steering can relax prior timing or compatibility clauses.
Preserve project requirements and resolve authoritative conflicts explicitly.
Carry exclusions through analysis, implementation, docs, tests, and review;
excluded work cannot become a derived blocker.

Inspect relevant current state and revalidate mutable evidence when required.
Completed tasks can leave the remaining-work view only with valid evidence;
their criteria and evidence remain in the contract. Reuse accepted unchanged
inputs without redundant experiments, reviewers, or artifact writes.

## Orchestration Plan

Drafting and requested saving are authorized outputs. If the composed request
also authorizes project-state preparation, plan that separate work first:

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

State preparation scope, ownership, checks, and authorization under
[prose rules](../../references/prose-rules.md). Present the plan and wait for
approval unless the session already authorizes it. Exit plan mode before
preparation. Do not treat revised goal text as present execution authority.

## 3. Produce the revised contract

Write the complete contract under [prose rules](../../references/prose-rules.md),
including original outcomes, current exclusions, dependencies, acceptance,
holds, and relevant recovery rules. Select applicable
[safeguards](../../references/safeguards.md). Challenge unnecessary inherited
guarantees while retaining actual obligations. Required independent review
must cover the exact revised contract; unavailable review stays UNVERIFIED.

Use the explicitly selected profile and binding under
[profile rules](../../references/profiles.md). Generic output is stdout-only;
save only when the request/profile selects it. An explicit stdout-only request
forbids all file writes, including temporary JSON input.

## 4. Render and hand off

Follow [rendering](../../references/rendering.md); send stdout-only input using
`render --input -`. Supply same-topic numbered predecessors in the dated
`goals/` layout through `predecessors`. Other-topic and legacy originals remain
sourced contract inputs; the helper does not migrate their layouts or infer
their counter identity. Report unresolved lineage rather than silently
restarting a series. Do not restart a topic's sequence on a new date.
Revised specifications get new immutable pairs. Identical reprints reuse the
revision and still print the whole payload.

Verify semantic coverage, companion identity, both character counts, and saved
bytes. Reply under [output contract](../../references/output.md) and
[prose rules](../../references/prose-rules.md), including every requirement's
disposition. Print the exact complete payload even after saving. If no payload
was returned, print the authored draft and concrete error as incomplete.
Stop before native activation, replacement, or execution.
