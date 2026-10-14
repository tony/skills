---
name: architecture
description: "Weave architecture: compare independent adversarial workers, then synthesize the best project architecture"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
argument-hint: "[--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--workers=subagents|model-clis] <architecture goal>"
disable-model-invocation: true
---

# Weave Architecture

Run an architecture or scaffolding task across independent adversarial workers, using host-native sub-agents by default or separate model CLIs when selected. After all workers finish, **cherry-pick the best conventions, skills, agents, and scaffolding from each worker** into one coherent architecture. Unlike `/weave:execute`, which targets feature implementation, this command targets project-level documentation, conventions, and structural artifacts. Unlike `/weave:prompt`, which picks one winner, it combines the best parts.

The architecture goal comes from `$ARGUMENTS`. If there are none, ask the user what they want scaffolded.

A request like `/weave:architecture apply the latest session` runs no workers: follow `../../references/mutating-run.md` (Apply a recorded session) with this skill's `adopt` and `update` commands from its final phase, and skip the other phases.

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

The plan follows `../../references/mutating-run.md` (Shared phases, Orchestration plan), with these items first:

1. **Goal scope**: what the architecture adds or changes, and what it must not touch
2. **Existing components**: the conventions file, skills, agents, hooks, and MCP or LSP servers already present, and the project layout
3. **Extra quality gates**: frontmatter and cross-reference validation

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`).

---

## Phase 1: Start the session

Follow `../../references/ensemble-core.md` (Start the session) with `--command architecture --mutating`; it asks each unresolved setting through `AskUserQuestion`. Then proceed per `../../references/mutating-run.md` (Shared phases). Explore the project: the existing conventions file, the component inventory (`skills/*/SKILL.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`, `.lsp.json`), directory layout, module boundaries, test framework, CI, and build system. The context packet holds the conventions summary, the component inventory, and known unknowns about the goal.

---

## Phase 2: Generate in parallel

The shared worker prompt body is:

> Generate project architecture artifacts for this codebase. Read the project's AGENTS.md/CLAUDE.md and structure first, and follow its conventions strictly.
>
> Goal: <the architecture goal>
>
> Produce any of: conventions-file updates (commit standards, quality gates), skill definitions (`skills/*/SKILL.md`), agent definitions (`agents/*.md`), architecture decision records, example code for core patterns, test harnesses for architectural invariants, and directory scaffolding. Put each artifact in its own file in the appropriate location, and run the quality gates when you finish.

---

## Phase 3: Analyze the architectures

Capture, run the gates, and record the pass per `../../references/mutating-run.md` (Shared phases). Also assess convention completeness (commit messages, testing, CI, code style, quality gates), skill quality (scope, description, tool restrictions), agent design (tool access, delegation), architectural coherence across artifacts, and whether test harnesses check real invariants; write the notes with the gate results. **Assess** per `ensemble-core.md` (Blind judging, Synthesis protocol), where the judge participant scores. The convergence mode is **file-by-file**. Its brief asks it, for each file any participant created or modified, to compare the original (`git show HEAD:<file>`, if it existed) with each snapshot, verify frontmatter, cross-references, tool names, and convention claims, and score each version per file. Select the artifacts per `../../references/mutating-run.md` (Shared phases), and write the analysis per `../../references/prose-rules.md`.

---

## Phase 4: Multi-pass refinement

Follow `../../references/mutating-run.md` (Refinement passes), repeating Phases 2 and 3.

---

## Phase 5: Apply the best architecture

Follow `../../references/mutating-run.md` (Apply gate and presentation): show the synthesis plan and wait before touching the main checkout.

1. Adopt the selected artifacts:

   ```console
   $ python3 <engine> adopt \
       --session "<session_dir>" \
       --pass <final N> \
       --pick <path>=<participant> \
       --delete <path>
   ```

   If `adopt` refuses, follow `../../references/mutating-run.md` (Apply gate and presentation).

2. Read the combined result and fix integration problems between files from different participants: naming, formatting, and cross-references (conventions name the right test commands, skills name real tools, agents name real skills).

3. Run the project's quality gates and check that every skill and agent has valid YAML frontmatter with `name` and `description`, that referenced tools exist, and that the conventions file agrees with the existing project structure. Then record the state:

   ```console
   $ python3 <engine> update \
       --session "<session_dir>" \
       --event synthesis_applied
   ```

4. Clean up per `../../references/mutating-run.md` (Shared phases) (Apply).

5. Read `../../references/present-results.md` and `../../references/results/architecture.md`, and apply them with `RESULT_KIND` = `architecture`, `ARTIFACT_PATH` = `<session_dir>/pass-NNNN/synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

---

## Finish

Follow `ensemble-core.md` (Finish). Report the artifacts applied and the participant each came from, the quality-gate result, and unavailable participants with their failure class.
