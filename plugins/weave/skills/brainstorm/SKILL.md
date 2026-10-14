---
name: brainstorm
description: "Use when asked to brainstorm, or a design question or open-ended problem needs multiple independent adversarial ideas."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--variants=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--preamble=...] [--workers=subagents|model-clis] <prompt>"
---

# Weave Brainstorm

Generate independent original responses from adversarial participants in parallel, with optional variants per participant. No scoring, ranking, or synthesis: the pool of originals is the product, and it can feed `/weave:refine` or `/weave:brainstorm-and-refine`. Host-native sub-agents are the default; separate model CLIs are optional. This command asks workers to leave your repository alone and runs them in snapshot worktrees; the repo guard checks the checkout within the scope in `ensemble-core.md` (Close the repo guard). Session artifacts live in the session directory, outside the repository.

The prompt comes from `$ARGUMENTS`. If there are none, ask the user what they want to brainstorm.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason. `../../references/ensemble-core.md` holds the shared steps this skill calls by section name.

## Worker selection

<!-- portable: ask-user-choice=headless-default -->

Before any other unresolved configuration choice or operational step, read
`../../references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Phase 1: Start the session

Follow `ensemble-core.md` (Start the session) with `--command brainstorm`, resolving variants per `ensemble-core.md` (Variants), which asks through `AskUserQuestion`. This command has no passes question. When the prompt asks for several distinct approaches and sets no variant count, use 3 variants without asking: one variant per participant would converge on the conventional design.

Build the context packet per `ensemble-core.md` (Context packet). Lead with conventions and the files the prompt touches.

---

## Phase 2: Generate the originals

The shared worker prompt body is:

> Respond to the following prompt about this codebase. Read relevant files to give a thorough, original response. Read CLAUDE.md/AGENTS.md for project conventions.
>
> Prompt: <the prompt>
>
> Provide a clear, well-structured response. Cite specific files and line numbers where relevant. Where the prompt asks for alternatives, make each one differ from the obvious design in mechanism (the underlying data structure or control flow), not in naming or detail.

Follow `ensemble-core.md` (Dispatch lanes) and (Variants), then (Close the repo guard).

---

## Phase 3: Present the originals

Read `../../references/present-results.md` and `../../references/results/brainstorm.md`, and apply them with `RESULT_KIND` = `brainstorm`, `ARTIFACT_PATH` = the session's `outputs/` directory, `SESSION_DIR`, `PASS_COUNT` = 1, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = null.

Reply with the hero and sections of `results/brainstorm.md` in that order, and nothing after Attribution. Head each response as `ensemble-core.md` (Variants) step 5 says. Do not group responses, count how many distinct designs they cover, merge them, or comment on overlap, rank them, or recommend one in your own voice.

---

## Finish

Follow `ensemble-core.md` (Finish).

## Rules

- Do not modify project files. Workers run in snapshot worktrees; the guard's scope is in `ensemble-core.md` (Close the repo guard).
