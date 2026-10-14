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

When the arguments ask to apply the latest session instead of giving a task, run no workers: follow `references/mutating-run.md` (Apply a recorded session) with this skill's `adopt` and `update` commands from its final phase, and skip the other phases.

`<engine>` is `references/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason. `references/ensemble-core.md` holds the shared steps this skill calls by section name.

This command needs a git repository with at least one commit, because workers run in worktrees and the engine stashes your uncommitted work. Without one, `init` fails: relay its `error` in one sentence, with no local paths, then tell the user to run it from a project checkout, and stop.

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

This command changes the working tree, so produce an orchestration plan before any phase.

The plan must contain:

1. **Task scope**: what the task changes, and what it must not touch
2. **Files**: the code the implementations must integrate with, and the test patterns
3. **Quality gates**: the commands from the project's AGENTS.md / CLAUDE.md
4. **Workers**: the backend, the lanes, and the pass count
5. **Apply policy**: the user's uncommitted changes are stashed before workers start and restored at the end; nothing reaches the main checkout until the user confirms the synthesis plan

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`). If plan mode is unavailable, write the plan as numbered steps in your response. With `ask-user-choice`, confirm once before proceeding. Without it (headless or one-shot runs), print the plan and continue without asking a text question: nothing reaches the main checkout before Phase 5, which has its own gate.

---

## Phase 1: Start the session

Follow `ensemble-core.md` (Start the session) with `--command execute --mutating`. The stash holds the user's uncommitted work until Phase 5. It asks each unresolved setting through `ask-user-choice`.

Explore the code the task touches, then build the context packet per `ensemble-core.md` (Context packet). Include snippets of code the implementations must integrate with, the relevant file list, test patterns, and known unknowns.

---

## Phase 2: Implement in parallel

The shared worker prompt body is:

> Implement the following task in this codebase. Read CLAUDE.md/AGENTS.md for project conventions and follow them strictly.
>
> Task: <the task>
>
> Follow all project conventions from AGENTS.md/CLAUDE.md. Run the project's quality gates after making changes.

Follow `ensemble-core.md` (Dispatch lanes) with `--mutating`, then (Close the repo guard). Every participant, including the `claude` lane under **model-clis**, works in its registered worktree.

---

## Phase 3: Analyze the implementations

1. **Capture** each worker's work. It writes `diffs/<participant>.patch` and snapshots of changed files to `files/<participant>/`, and lists `changed` and `deleted` paths:

   ```console
   $ python3 <engine> capture \
       --session "<session_dir>" \
       --pass <N> \
       --participant <participant>
   ```

2. **Quality gates.** In each participant's registered worktree, run the project's gates from AGENTS.md / CLAUDE.md: formatter, linter, type checker, tests. Write pass/fail per gate and participant to `pass-NNNN/quality-gates.md`.

3. **Judge** per `ensemble-core.md` (Blind judging, Synthesis protocol). The convergence mode is **file-by-file**. For each file any participant modified, read the original (`git show HEAD:<file>`) and each snapshot, verify what the code does against what the participant claims, score each version with the rubric per file, and select the best version per file. The best versions can come from different participants. Fix cross-file consistency when converging.

4. Write the file-by-file analysis (selected version per file, scores, deleted paths, quality-gate failures) to `<session_dir>/pass-NNNN/synthesis.md` per `references/prose-rules.md`.

5. Record the pass (`update --completed-passes <N> --event pass_complete`). Do not render results yet: the user's stash is still held, so presentation waits for Phase 5.

---

## Phase 4: Multi-pass refinement

Follow `references/mutating-run.md` (Refinement passes), repeating Phases 2 and 3. Also target per-file low scores and re-score only affected files.

---

## Phase 5: Apply the best implementation

Follow `references/mutating-run.md` (Apply gate and presentation): show the synthesis plan and wait before touching the main checkout.

1. Copy the chosen snapshot of each file into the main checkout and remove each path whose selected version is a deletion. Repeat `--pick` and `--delete` per path. Snapshots, not worktrees, are the source, so this works after worktrees are gone:

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

4. Remove the worktrees and restore the user's changes with `stash-restore` (`references/mutating-run.md`, Remove worktrees and restore the stash), checking `git diff --stat HEAD` against the synthesis plan. Continue to step 5 after a stash conflict.

5. Read `references/present-results.md` and `references/execute.md`, and apply them with `RESULT_KIND` = `execute`, `ARTIFACT_PATH` = `<session_dir>/pass-NNNN/synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

---

## Finish

Follow `ensemble-core.md` (Finish). Report the files applied and the participant each came from, the quality-gate result, and unavailable participants with their failure class.

## Rules

- Never apply a synthesis that fails the quality gates, and never apply one before the user confirms the plan.
- Workers are told to stay in their registered worktrees. Recorded drift stops adoption and cleanup until the user decides (`references/mutating-run.md`).


## Portability notes

- `ask-user-choice` — follow the source's choice contract. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it. Honor a documented headless default when the source defines one; otherwise print a numbered list and wait for a numbered reply. Never invent a choice.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
