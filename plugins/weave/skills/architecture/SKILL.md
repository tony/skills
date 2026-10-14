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

When the arguments ask to apply the latest session instead of giving a task, run no workers: follow `../../references/mutating-run.md` (Apply a recorded session) with this skill's `adopt` and `update` commands from its final phase, and skip the other phases.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason. `../../references/ensemble-core.md` holds the shared steps this skill calls by section name.

This command needs a git repository with at least one commit, because workers run in worktrees and the engine stashes your uncommitted work. Without one, `init` fails: relay its `error` in one sentence, with no local paths, then tell the user to run it from a project checkout, and stop.

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

This command changes the working tree, so produce an orchestration plan before any phase.

The plan must contain:

1. **Goal scope**: what the architecture adds or changes, and what it must not touch
2. **Existing components**: the conventions file, skills, agents, hooks, and MCP or LSP servers already present, and the project layout
3. **Quality gates**: the commands from the project's AGENTS.md / CLAUDE.md, plus frontmatter and cross-reference validation
4. **Workers**: the backend, the lanes, and the pass count
5. **Apply policy**: the user's uncommitted changes are stashed before workers start and restored at the end; nothing reaches the main checkout until the user confirms the synthesis plan

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`). If plan mode is unavailable, write the plan as numbered steps in your response. With `AskUserQuestion`, confirm once before proceeding. Without it (headless or one-shot runs), print the plan and continue without asking a text question: nothing reaches the main checkout before Phase 5, which has its own gate.

---

## Phase 1: Start the session

Follow `ensemble-core.md` (Start the session) with `--command architecture --mutating`. The stash holds the user's uncommitted work until Phase 5. It asks each unresolved setting through `AskUserQuestion`.

Explore the project: the existing conventions file, the component inventory (`skills/*/SKILL.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`, `.lsp.json`), directory layout, module boundaries, test framework, CI, and build system. Build the context packet per `ensemble-core.md` (Context packet), with the conventions summary, the component inventory, and known unknowns about the goal.

---

## Phase 2: Generate in parallel

The shared worker prompt body is:

> Generate project architecture artifacts for this codebase. Read the project's AGENTS.md/CLAUDE.md and structure first, and follow its conventions strictly.
>
> Goal: <the architecture goal>
>
> Produce any of: conventions-file updates (commit standards, quality gates), skill definitions (`skills/*/SKILL.md`), agent definitions (`agents/*.md`), architecture decision records, example code for core patterns, test harnesses for architectural invariants, and directory scaffolding. Put each artifact in its own file in the appropriate location. Run the project's quality gates after making changes.

Follow `ensemble-core.md` (Dispatch lanes) with `--mutating`, then (Close the repo guard). Every participant, including the `claude` lane under **model-clis**, works in its registered worktree.

---

## Phase 3: Analyze the architectures

1. **Capture** each worker's work. It writes `diffs/<participant>.patch` and snapshots of changed files to `files/<participant>/`, and lists `changed` and `deleted` paths:

   ```console
   $ python3 <engine> capture \
       --session "<session_dir>" \
       --pass <N> \
       --participant <participant>
   ```

2. **Quality gates.** In each participant's registered worktree, run the project's gates: formatter, linter, type checker, tests. Also assess convention completeness (commit messages, testing, CI, code style, quality gates), skill quality (scope, description, tool restrictions), agent design (tool access, delegation), architectural coherence across artifacts, and whether test harnesses check real invariants. Write pass/fail and notes per participant to `pass-NNNN/quality-gates.md`.

3. **Judge** per `ensemble-core.md` (Blind judging, Synthesis protocol); the judge participant, not the coordinator, scores. The convergence mode is **file-by-file**. Its brief names `files/<participant>/` and the quality-gate results as readable, and asks it, for each file any participant created or modified, to compare the original (`git show HEAD:<file>`, if it existed) with each snapshot, verify frontmatter, cross-references, tool names, and convention claims, and score each version per file. Select the best version per file from its scores. The best versions can come from different participants. Fix cross-file consistency when converging.

4. Write the file-by-file analysis (selected version per file, scores, deleted paths, quality-gate failures) to `<session_dir>/pass-NNNN/synthesis.md` per `../../references/prose-rules.md`.

5. Record the pass (`update --completed-passes <N> --event pass_complete`). Do not render results yet: the user's stash is still held, so presentation waits for Phase 5.

---

## Phase 4: Multi-pass refinement

Follow `../../references/mutating-run.md` (Refinement passes), repeating Phases 2 and 3. Also target per-file low scores and re-score only affected files.

---

## Phase 5: Apply the best architecture

Follow `../../references/mutating-run.md` (Apply gate and presentation): show the synthesis plan and wait before touching the main checkout.

1. Copy the chosen snapshot of each file into the main checkout and remove each path whose selected version is a deletion. Repeat `--pick` and `--delete` per path. Snapshots, not worktrees, are the source, so this works after worktrees are gone:

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

4. Remove the worktrees and restore the user's changes with `stash-restore` (`../../references/mutating-run.md`, Remove worktrees and restore the stash), checking `git diff --stat HEAD` against the synthesis plan. Continue to step 5 after a stash conflict.

5. Read `../../references/present-results.md` and `../../references/results/architecture.md`, and apply them with `RESULT_KIND` = `architecture`, `ARTIFACT_PATH` = `<session_dir>/pass-NNNN/synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

---

## Finish

Follow `ensemble-core.md` (Finish). Report the artifacts applied and the participant each came from, the quality-gate result, and unavailable participants with their failure class.

## Rules

- Never apply a synthesis that fails the quality gates, and never apply one before the user confirms the plan.
- Workers are told to stay in their registered worktrees. Recorded drift stops adoption and cleanup until the user decides (`../../references/mutating-run.md`).
