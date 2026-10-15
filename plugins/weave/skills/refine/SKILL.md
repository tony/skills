---
name: refine
description: "Use when asked to refine a draft, iterate on code until cleaner, or polish a README through repeated critique and improvement."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion"]
argument-hint: "[--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--judge=host|round-robin] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] <text or file path>"
---

# Weave Refine

Improve an artifact through independent adversarial critique and weaving. Every pass, all participants critique and improve the artifact, a judge picks the best version, the weave folds in the runners-up's strengths, and the woven result goes back to all participants.

The artifact comes from `$ARGUMENTS`: an existing file path (read it) or inline text. If there are none, ask the user what to refine.

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

Follow `../../references/ensemble-core.md` (Start the session) with `--command refine`. It asks each unresolved setting through `AskUserQuestion`.

Read the artifact from `prompt`, and write it to `<session_dir>/original.md`. Build the context packet per `ensemble-core.md` (Context packet), leading with conventions and key snippets from the artifact's domain.

---

## Phase 2: Pass 1, critique and improve

The shared worker prompt body is:

> You are reviewing an artifact for iterative refinement. Produce three sections.
>
> ## Critique
> What is strong, weak, or missing? Be specific: quote passages and cite concrete issues.
>
> ## Improved Version
> Your complete improved version, as a full replacement, not a diff. Cut filler and padding, not the claims the artifact makes; do not add placeholders for facts the artifact lacks.
>
> ## Rationale
> Why you made each change, tied to a finding in your critique.
>
> ---
>
> **Artifact to refine:**
>
> <the artifact text>

Follow `ensemble-core.md` (Dispatch lanes) with this body, then (Close the repo guard). A participant whose output lacks the three sections is parsed as written, and the judge notes the gap.

---

## Phase 3: Judge, weave, distribute

Follow `../../references/refine-cycle.md` for pass 1, with the candidates in `pass-0001/outputs/` and the judge mode from `judge`. For every later pass up to `passes`, the cycle's Distribute step has already written the prompt, so dispatch it as in Phase 2 (with the new pass number), close the repo guard, and run the cycle again.

---

## Phase 4: Deslop and present

Follow `../../references/refine-cycle.md` (Deslop, present, and finish) with `../../references/deslop-pass.md`, `../../references/present-results.md`, `RESULT_KIND` = `refine` and `../../references/results/refine.md`. Inline-text input gets the same shape: a hero line first, then the four listed headings, with no title line or other headings. Write the reply per `../../references/prose-rules.md`.

## Rules

- Verify every model claim against the codebase before it enters the weave, and cite files and line numbers.
- When models contradict each other, check the code and keep the correct version.
