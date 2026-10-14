---
name: weave-execute
description: >-
  Weave execute: compare independent adversarial implementations, then
  synthesize their best parts
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
metadata:
  argument-hint: "[--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--workers=subagents|model-clis] <task description>"
  source: "plugins/weave/skills/execute/SKILL.md"
---

# Weave Execute

Run a task across independent adversarial workers, using host-native sub-agents by default or separate model CLIs when selected. Each sub-agent or external worker uses its own git worktree. After all workers finish, **synthesize the best elements of every implementation** into one result. Unlike the `weave-prompt` skill, which picks one winner, this command cherry-picks the best parts of each worker's work.

The task comes from `$ARGUMENTS`. If there are none, ask the user what they want implemented.

A request like `this skill apply the latest session` runs no workers: follow `references/mutating-run.md` (Apply a recorded session) with this skill's `adopt` and `update` commands from its final phase, and skip the other phases.

`<engine>` is `references/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`.

If context already proves there is no repository or no commit, stop there.
Use only: "Stopped: execute needs a project checkout with at least one commit."
Then one bullet: "Run it from that checkout." Do not explain the stash or
worktree machinery or ask the user to create a commit.

## Worker selection



Before any other unresolved configuration choice or operational step, read
`references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Produce the plan per `references/mutating-run.md` (Shared phases, Orchestration plan).

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`).

---

## Phase 1: Start the session

Follow `references/ensemble-core.md` (Start the session) with `--command execute --mutating`; it asks each unresolved setting through `ask-user-choice`. Then start and dispatch per `references/mutating-run.md` (Shared phases).

---

## Phase 2: Implement in parallel

Use the worker prompt body of `references/mutating-run.md` (Shared phases), with the task as `<the task>`.

---

## Phase 3: Analyze the implementations

Capture, run the gates, and record the pass per `references/mutating-run.md` (Shared phases). **Judge** per `ensemble-core.md` (Blind judging, Synthesis protocol). The convergence mode is **file-by-file**. Its brief asks it, for each file any participant modified, to compare the original (`git show HEAD:<file>`) with each snapshot, verify what the code does against what the participant claims, and score each version per file. Select the files per `references/mutating-run.md` (Shared phases), and write the analysis per `references/prose-rules.md`.

---

## Phase 4: Multi-pass refinement

Follow `references/mutating-run.md` (Refinement passes), repeating Phases 2 and 3.

---

## Phase 5: Apply the best implementation

Follow `references/mutating-run.md` (Apply gate and presentation): show the synthesis plan and wait before touching the main checkout.

1. Adopt the selected files:

   ```console
   $ python3 <engine> adopt \
       --session "<session_dir>" \
       --pass <final N> \
       --pick <path>=<participant> \
       --delete <path>
   ```

   If `adopt` refuses, follow `references/mutating-run.md` (Apply gate and presentation).

2. Read the combined result and fix integration problems: imports, signatures, and API mismatches between files from different participants; naming, docstring, and import style per the project's conventions.

3. Run the project's quality gates, then record the state:

   ```console
   $ python3 <engine> update \
       --session "<session_dir>" \
       --event synthesis_applied
   ```

4. Clean up per `references/mutating-run.md` (Shared phases) (Apply).

5. Read `references/present-results.md` and `references/execute.md`, and apply them with `RESULT_KIND` = `execute`, `ARTIFACT_PATH` = `<session_dir>/pass-NNNN/synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

---

## Finish

Follow `ensemble-core.md` (Finish). Report the files applied and the participant each came from, the quality-gate result, and unavailable participants with their failure class.


## Portability notes

- `ask-user-choice` — follow the source's choice contract. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it. Honor a documented headless default when the source defines one; otherwise print a numbered list and wait for a numbered reply. Never invent a choice.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
