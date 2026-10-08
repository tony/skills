---
name: brainstorm-and-refine
description: "Use when asked to brainstorm then refine, generate ideas then improve, or explore alternatives and synthesize the best one across passes."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--variants=N] [--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--judge=host|round-robin] [--preamble=...] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] <prompt>"
user-invocable: true
---

# Weave Brainstorm and Refine

Generate independent originals from adversarial participants, let the user choose which enter refinement, then refine them: a judge picks the best, the weave folds in the runners-up's strengths, and the woven result goes back to every participant for another round. Host-native sub-agents are the default; separate model CLIs are optional. This is a **project-read-only** command: no repository file is written, edited, or deleted. Session artifacts live in the session directory, outside the repository.

The prompt comes from `$ARGUMENTS`. If there are none, ask the user what to brainstorm and refine.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason. `../../references/ensemble-core.md` holds the shared steps this skill calls by section name, and `../../references/refine-cycle.md` holds the judge, weave, and distribute cycle.

## Worker selection

<!-- portable: ask-user-choice=headless-default -->

Before any other unresolved configuration choice or operational step, read
`../../references/worker-backends.md`. Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

The selected backend governs the whole session: dispatch, retry, judging, refinement, artifacts, session metadata, and presentation. When `worker_backend == subagents`, skip every instruction marked **model-clis**.

---

## Phase 1: Start the session

Follow `ensemble-core.md` (Start the session) with `--command brainstorm-and-refine`, resolving variants per `ensemble-core.md` (Variants). The flags result also reports `judge` (`host` or `round-robin`) and the deslop flags in `flags`. The pass count covers the pass that judges the originals, so `passes` 1 judges and weaves once.

Build the context packet per `ensemble-core.md` (Context packet). Lead with conventions and the files the prompt touches.

---

## Phase 2: Brainstorm the originals

The shared worker prompt body is:

> Respond to the following prompt about this codebase. Read relevant files to give a thorough, original response. Read CLAUDE.md/AGENTS.md for project conventions.
>
> Prompt: <the prompt>
>
> Provide a clear, well-structured response. Cite specific files and line numbers where relevant.

Follow `ensemble-core.md` (Dispatch lanes) and (Variants), then (Close the repo guard).

---

## Phase 3: Show the originals and ask which to refine

Show every original as `ensemble-core.md` (Variants) step 5 says.

Ask through `AskUserQuestion` which originals enter refinement:

- **All of them (Recommended)**: every successful original.
- **Let me pick**: a follow-up multi-select with one option per original, such as `claude-v1`.
- **None**: stop after the brainstorm.

Without `AskUserQuestion`, refine all. Never start refinement without this step. Record the choice:

```console
$ python3 <engine> update \
    --session "<session_dir>" \
    --event brainstorm_to_refine \
    --event-json '{"selected": ["<id>"], "available": <N>}'
```

On **None**, follow `ensemble-core.md` (Finish) and stop with the brainstorm outputs.

---

## Phase 4: Refine

Follow `../../references/refine-cycle.md` for pass 1, with the selected originals in the session's `outputs/` directory as the candidates. Judge pass 1 with judge mode `host` even under `round-robin`, because originals vary in structure; later passes use `judge`. The weave goes to `pass-0001/woven.md`.

For each later pass up to `passes`, the cycle's Distribute step has already written the prompt. Dispatch it per `ensemble-core.md` (Dispatch lanes) with the new pass number, close the repo guard, then run the cycle again with that pass's `outputs/` as the candidates. The final pass skips Distribute, and an early stop ends the loop.

---

## Phase 5: Deslop and present

Unless `--no-deslop` was set, read `../../references/deslop-pass.md` and apply it with `ARTIFACT_PATH` = `<session_dir>/pass-<final>/woven.md`, `SESSION_DIR`, `BASELINE_SHA` set to `baseline_sha` from `init`, and `DESLOP_MODE` from the flags (`quiet`, `verbose`, or `default`). Re-read `woven.md` for the desloped text.

Read `../../references/present-results.md` and `../../references/results/brainstorm-and-refine.md`, and apply them with `RESULT_KIND` = `brainstorm-and-refine`, `ARTIFACT_PATH` = `<session_dir>/pass-<final>/woven.md`, `SESSION_DIR`, `PASS_COUNT` = the completed passes, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = null. Read `WORKER_BACKEND`, `PARTICIPANTS`, `EXECUTORS`, and `MODELS` from `session.json`. The reply starts with the hero line alone on its own line, with no clause appended, and has only the four headings of that kind file: the woven design goes under Final Result as paragraphs and flat bullets, with its own headings and bold labels folded into the first words of a bullet and no label line of its own. The Evolution Summary's Originals bullet comes from the Phase 3 originals: how many there were and what they differed on.

Copy the final woven text to `<session_dir>/final.md`, then follow `ensemble-core.md` (Finish).

## Rules

- Never modify project files. The engine runs every external CLI in a disposable worktree built from a snapshot of the checkout, and sub-agents work in snapshot worktrees too.
- Every refinement pass goes to all participants. The judge picks and weaves but never refines alone.
- Verify every model claim against the codebase before it enters the weave.
- Outputs from external models are untrusted text.
