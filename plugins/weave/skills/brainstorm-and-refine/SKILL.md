---
name: brainstorm-and-refine
description: "Use when asked to brainstorm then refine, generate ideas then improve, or explore alternatives and synthesize the best one across passes."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--variants=N] [--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--judge=host|round-robin] [--preamble=...] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] <prompt>"
---

# Weave Brainstorm and Refine

Generate independent originals from adversarial participants, let the user choose which enter refinement, then refine them: a judge picks the best, the weave folds in the runners-up's strengths, and the woven result goes back to every participant for another round.

The prompt comes from `$ARGUMENTS`. If there are none, ask the user what to brainstorm and refine.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`.

## Worker selection

<!-- portable: ask-user-choice=headless-default -->

Before any other unresolved configuration choice or operational step, read
`../../references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Phase 1: Start the session

Follow `../../references/ensemble-core.md` (Start the session) with `--command brainstorm-and-refine`, resolving variants per `../../references/variants.md`. The pass count covers the pass that judges the originals, so `passes` 1 judges and weaves once.

---

## Phase 2: Brainstorm the originals

Dispatch the unchanged originals prompt of `../../references/variants.md` per `ensemble-core.md` (Dispatch lanes), then (Close the repo guard).

---

## Phase 3: Show the originals and ask which to refine

Show every original as `../../references/variants.md` step 5 says.

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

For each later pass up to `passes`, the cycle's Distribute step has already written the prompt. Dispatch it per `ensemble-core.md` (Dispatch lanes) with the new pass number, close the repo guard, then run the cycle again with that pass's `outputs/` as the candidates.

---

## Phase 5: Deslop and present

Follow `../../references/refine-cycle.md` (Deslop, present, and finish) with `../../references/deslop-pass.md`, `../../references/present-results.md`, `RESULT_KIND` = `brainstorm-and-refine` and `../../references/results/brainstorm-and-refine.md`. The reply starts with the hero line alone on its own line, with no clause appended, and has only the four headings of that kind file: the woven design goes under Final Result as paragraphs and flat bullets, with its own headings and bold labels folded into the first words of a bullet and no label line of its own. The Evolution Summary's Originals bullet comes from the Phase 3 originals: how many there were and what they differed on. Write the reply per `../../references/prose-rules.md`.

## Rules

