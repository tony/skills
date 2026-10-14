---
name: prompt
description: "Weave prompt: compare independent adversarial implementations, then adopt the single best one"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
argument-hint: "[--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--workers=subagents|model-clis] <implementation prompt>"
disable-model-invocation: true
---

# Weave Prompt

Run an implementation prompt across independent adversarial workers, using host-native sub-agents by default or separate model CLIs when selected. After all workers finish, compare the implementations and **adopt the single best one**, whole. Unlike `/weave:execute`, which cherry-picks the best parts of each worker's work, this command never merges code across implementations.

The implementation prompt comes from `$ARGUMENTS`. With no prompt, ask the user what they want implemented.

A request like `/weave:prompt apply the latest session` runs no workers: follow `../../references/mutating-run.md` (Apply a recorded session) with this skill's `adopt` and `update` commands from its final phase, and skip the other phases.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`.

## Worker selection

<!-- portable: ask-user-choice=headless-default -->

Before any other unresolved configuration choice or operational step, read
`../../references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Write the plan per `../../references/mutating-run.md` (Shared phases, Orchestration plan).

Present it, wait for approval, and exit plan mode (`ExitPlanMode`).

---

## Phase 1: Start the session

Follow `../../references/ensemble-core.md` (Start the session) with `--command prompt --mutating`; it asks each unresolved setting through `AskUserQuestion`. Dispatch per `../../references/mutating-run.md` (Shared phases).

---

## Phase 2: Implement in parallel

Use the worker prompt body of `../../references/mutating-run.md` (Shared phases), with the implementation prompt as `<the task>`.

---

## Phase 3: Compare the implementations

Capture, run the gates, and record the pass per `../../references/mutating-run.md` (Shared phases). **Compare** per `ensemble-core.md` (Blind judging, Synthesis protocol), where the judge participant scores. The convergence mode is **pick-winner**: the highest-scoring implementation wins, and no code merges across implementations. Its brief asks it to verify what each implementation does against what its participant claims. A failing quality gate caps that implementation's Correctness at 3. Write the comparison (scores per implementation, quality-gate results, the winner and why) to `<session_dir>/pass-NNNN/synthesis.md` per `../../references/prose-rules.md`.

---

## Phase 4: Multi-pass refinement

Follow `../../references/mutating-run.md` (Refinement passes), repeating Phases 2 and 3.

---

## Phase 5: Adopt the chosen implementation

Follow `../../references/mutating-run.md` (Apply gate and presentation): show the comparison and the recommended winner, and let the user choose and wait before touching the main checkout.

1. Copy everything the winner captured into the main checkout, deletions included:

   ```console
   $ python3 <engine> adopt \
       --session "<session_dir>" \
       --pass <final N> \
       --all <winner>
   ```

   If `adopt` refuses, follow `../../references/mutating-run.md` (Apply gate and presentation).

2. Run the project's quality gates, then record the state:

   ```console
   $ python3 <engine> update \
       --session "<session_dir>" \
       --event adoption_applied
   ```

3. Clean up per `../../references/mutating-run.md` (Shared phases) (Apply), checking `git diff --stat HEAD` against the winner's patch.

4. Read `../../references/present-results.md` and `../../references/results/prompt.md`, and apply them with `RESULT_KIND` = `prompt`, `ARTIFACT_PATH` = `<session_dir>/pass-NNNN/synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

---

## Finish

Follow `ensemble-core.md` (Finish). Report the winning participant, the quality-gate result, and unavailable participants with their failure class.
