---
name: brainstorm
description: "Use when asked to brainstorm, or a design question or open-ended problem needs multiple independent adversarial ideas."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--variants=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--preamble=...] [--workers=subagents|model-clis] <prompt>"
---

# Weave Brainstorm

Generate independent original responses from adversarial participants in parallel, with optional variants per participant. No scoring, ranking, or synthesis: the pool of originals is the product, and it can feed `/weave:refine` or `/weave:brainstorm-and-refine`.

The prompt comes from `$ARGUMENTS`. If there are none, ask the user what they want to brainstorm.

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

Follow `../../references/ensemble-core.md` (Start the session) with `--command brainstorm`, resolving variants per `../../references/variants.md`, which asks through `AskUserQuestion`. This command has no passes question. When the prompt asks for several distinct approaches and sets no variant count, use 3 variants without asking: one variant per participant would converge on the conventional design.

---

## Phase 2: Generate the originals

Dispatch per `ensemble-core.md` (Dispatch lanes), then (Close the repo guard), using the originals prompt of `../../references/variants.md` and appending: "Where the prompt asks for alternatives, make each one differ from the obvious design in mechanism (the underlying data structure or control flow), not in naming or detail."

---

## Phase 3: Present the originals

Read `../../references/present-results.md` and `../../references/results/brainstorm.md`, and apply them with `RESULT_KIND` = `brainstorm`, `ARTIFACT_PATH` = the session's `outputs/` directory, `SESSION_DIR`, `PASS_COUNT` = 1, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = null. Write the reply per `../../references/prose-rules.md`.

Reply with the hero and sections of `results/brainstorm.md` in that order, and nothing after Attribution. Head each response as `../../references/variants.md` step 5 says. Do not group responses, count how many distinct designs they cover, merge them, or comment on overlap, rank them, or recommend one in your own voice.

---

## Finish

Follow `ensemble-core.md` (Finish).
