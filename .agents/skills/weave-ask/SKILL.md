---
name: weave-ask
description: >-
  Weave question: ask independent adversarial workers in parallel, then
  synthesize the best answer
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
metadata:
  argument-hint: "[--cascade] [--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] <question>"
  source: "plugins/weave/skills/ask/SKILL.md"
---

# Weave Ask

Ask independent adversarial workers the same question in parallel, then synthesize the best answer.

The question comes from `$ARGUMENTS`. With none, ask the user what they want to know.

`<engine>` is `references/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`.

## Worker selection



Before any other unresolved configuration choice or operational step, read
`references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Phase 1: Start the session

Follow `references/ensemble-core.md` (Start the session) with `--command ask`. It asks each unresolved setting through `ask-user-choice`.

Build the context packet per `ensemble-core.md` (Context packet). Lead with conventions and relevant files, and include changed files only when the question concerns branch changes. Without a repository, say "no repository" up front and answer from what the question and any files the user names provide; state what could not be checked rather than inventing code.

---

## Phase 2: Cascade gate (only with `--cascade`)

Read `references/ensemble-techniques.md` (Technique 1) and apply it: run the Maintainer lane from Phase 3 alone, self-verify with the Verify Claims step, and evaluate the five escalation triggers. On **early-exit**, skip the other lanes, blind judging, and scoring; run the Critic, then go to Phase 6 with `CASCADE_STATE` = `early-exit`. On **escalate** (or user escalation from the panel), continue to Phase 3 and reuse the cheap-pass output as the Maintainer lane.

---

## Phase 3: Ask all workers in parallel

The shared worker prompt body is:

> Answer the following question about this codebase. Read relevant files to give a thorough, accurate answer. Read CLAUDE.md/AGENTS.md for project conventions.
>
> Question: <the question>
>
> Provide a clear, well-structured answer, citing files and line numbers.

Follow `ensemble-core.md` (Dispatch lanes) with this body, then (Close the repo guard).

---

## Phase 4: Synthesize the best answer

Apply `ensemble-core.md` (Blind judging, Synthesis protocol) and `references/consensus-map.md` to this pass's outputs. The convergence mode is **Merge**.

Write the synthesis to `<session_dir>/pass-NNNN/synthesis.md` per `references/prose-rules.md`.

Render nothing yet; Phase 6 presents the result once, after the last pass.

---

## Phase 5: Multi-pass refinement

Skip this phase when `passes` is 1. Otherwise run the later passes with Technique 2 of `references/ensemble-techniques.md` and `ensemble-core.md` (Later passes).

The final pass's `synthesis.md` (pass 1 when `passes` is 1) feeds Phase 6, with a **Refinement Notes** section on what was deepened, corrected, or confirmed.

---

## Phase 6: Polish and present

1. Unless `--no-deslop` was set, read `references/deslop-pass.md` and apply it once, with `ARTIFACT_PATH` set to the final pass's `synthesis.md`, `SESSION_DIR`, `BASELINE_SHA` set to `baseline_sha` from `init`, and `DESLOP_MODE` from the flags (`quiet`, `verbose`, or `default`). Re-read `synthesis.md` for the desloped text.

2. Read `references/present-results.md` and `references/ask.md`, and apply them with `RESULT_KIND` = `ask`, `ARTIFACT_PATH` = the final `synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = `passes`, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json` (null when only one worker answered or the cascade exited early), `CASCADE_STATE` = `early-exit`, `escalated`, or null without `--cascade`.

---

## Finish

Follow `ensemble-core.md` (Finish).

## Rules

- Verify every model claim against the codebase before it enters the synthesis, and cite files and line numbers.
- When models contradict each other, check the code and state which is correct.


## Portability notes

- `ask-user-choice` — follow the source's choice contract. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it. Honor a documented headless default when the source defines one; otherwise print a numbered list and wait for a numbered reply. Never invent a choice.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
