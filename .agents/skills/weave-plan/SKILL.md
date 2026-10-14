---
name: weave-plan
description: >-
  Weave planning: compare independent adversarial plans, then synthesize the
  best one
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion", "EnterPlanMode"]
metadata:
  argument-hint: "[--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] <task description>"
  source: "plugins/weave/skills/plan/SKILL.md"
---

# Weave Plan

Get implementation plans from independent adversarial workers in parallel, then synthesize the best plan. Host-native sub-agents are the default; separate model CLIs are optional. The output is a finalized plan file ready for execution.

This command asks workers to leave your repository alone and runs them in snapshot worktrees; the repo guard checks the checkout within the scope in `ensemble-core.md` (Close the repo guard). Session artifacts live in the session directory, outside your repository.

The task comes from `$ARGUMENTS`; if there are none, ask the user what they want planned.

`<engine>` is `references/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason. `references/ensemble-core.md` holds the shared steps this skill calls by section name.

## Worker selection



Before any other unresolved configuration choice or operational step, read
`references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Phase 0: Enter plan mode

Call `EnterPlanMode` immediately and stay in it: the final output is the host's plan file, and the user approves execution from it. Never call `ExitPlanMode`. Emit `Plan mode active: drafting implementation plan.`

In plan mode the main agent reads (`Read`, `Grep`, `Glob`), asks questions, launches Task agents, and writes the plan file. It runs read-only engine commands (`flags`, `context`, `judge-parse`) directly. Everything else that writes goes to a session agent: a `general-purpose` Task agent with `mode: "default"`. Batch a phase's commands into one task and give it the exact engine commands or file contents; it returns each command's JSON verbatim. This covers `init`, `prompt`, `worktrees`, `labels`, `packet`, `update`, `guard`, `participant`, and every file written under `<session_dir>`.

`init` runs from the live checkout. For everything after it, the session agent starts a `session` snapshot participant (`ensemble-core.md`, Close the repo guard), runs each shell command with the returned prefix, writes files with `claim` or `write`, and runs `participant finish` before it returns. A failed finish is a halt.

Without plan mode (headless runs), proceed normally and present the final plan as markdown text instead of a plan file.

---

## Phase 1: Start the session

1. Read the project's CLAUDE.md / AGENTS.md. Explore the files most relevant to the task for architecture, patterns, and constraints.

2. Follow `ensemble-core.md` (Start the session) with `--command plan`. Run `init` through the session agent. The flags result also reports the deslop flags in `flags`. It asks each unresolved setting through `ask-user-choice`.

3. Build the context packet per `ensemble-core.md` (Context packet), using `context` for the repo state. Without a repository, say "no repository" up front and plan as greenfield: no existing files, conventions, or tests are assumed. Lead with the changed files and their diff stats, key snippets of code the plan touches, and known unknowns the plan should address. The session agent writes it to `<session_dir>/context-packet.md`.

---

## Phase 2: Get plans in parallel

The shared worker prompt body is:

> Create a detailed implementation plan for the following task. Read the codebase for the existing architecture, patterns, and conventions, and the project's CLAUDE.md/AGENTS.md for standards.
>
> Task: <the task>
>
> Your plan must include:
> 1. **Files to create or modify**: every file, with the changes it needs
> 2. **Implementation sequence**: ordered steps with dependencies between them
> 3. **Architecture decisions**: key choices justified by existing patterns
> 4. **Test strategy**: tests to add or extend, using the project's test patterns
> 5. **Risks and edge cases**: potential problems and mitigations
> 6. **Commit boundaries**: each step is one atomic commit, with a commit message (no `Co-Authored-By`, no tool trailer, no emoji) and the quality gates (lint, format, type-check, fast tests) to verify before committing
>
> Be specific: reference actual files, functions, and patterns from the codebase. Separate the user's requirements from proposed defaults. Explain how normal, failure and capacity paths satisfy each hard constraint; a stated hard limit never sits beside fail-open behavior without saying which applies. State the assumptions behind resource estimates, and label an estimate that covers only part of the cost as partial, never as a total.
>
> Length cap: at most 700 words in total. One line per file and per step; no code blocks, no rejected alternatives, no restating the task.

Follow `ensemble-core.md` (Dispatch lanes) with this body, running the engine commands through the session agent, then (Close the repo guard). If only one lane responds, continue with it alone and say so.

---

## Phase 3: Synthesize the best plan

Apply `ensemble-core.md` (Blind judging, Synthesis protocol) to this pass's outputs, with the default rubric. The convergence mode is **Merge**: verified points first, agreed ones leading, then adjudicated resolutions, then the best unique contributions ordered by score, with unverified claims stripped. The main agent reads the packet (`ensemble-core.md`, Blind judging) and judges; the session agent writes the artifacts.

During Verify Claims, record the task's hard constraints in `verification.md`
and trace the proposed design through normal operation, failures and capacity
limits. A fallback must satisfy the same requirement as the main path;
agreement between workers cannot authorize an exception. Keep an unresolved
policy choice explicit and block the affected step until the user decides.
For a quantitative bound, verify its units, representation, scope and omitted
costs. A payload calculation does not bound containers, keys or total process
memory. Recheck these constraints after integrating critic findings.

The synthesis holds at most 900 words: state each agreed step once and drop worker prose.

Steps 2 to 4 run on the final pass only (pass 1 when `passes` is 1, else the last pass of Phase 4), so the plan is rendered once. In this order:

1. Have the session agent read `references/present-results.md` and `references/plan.md`, then write the synthesis to `<session_dir>/pass-NNNN/synthesis.md` using that result contract and `references/prose-rules.md`. Supply those same references to the agent that writes the final plan file. Raw critic deltas stay in `critic.md`; the plan's Critic Findings uses the final risk/safeguard format from the result template. The plan must tell the executor to run the project's quality gates before each commit, and to write commit messages with no `Co-Authored-By` line, no "Generated with" or other tool trailer, and no emoji.

2. Unless `--no-deslop` was set, deslop through the session agent: plan mode makes the main agent read-only, and the pass needs `Edit` and a file copy. Tell the session agent to read `references/deslop-pass.md` and apply it with `ARTIFACT_PATH` set to that file, `SESSION_DIR`, `BASELINE_SHA` set to `baseline_sha` from `init`, and `DESLOP_MODE` from the flags, and to return the one-line summary. Re-read `synthesis.md` for the desloped plan. The summary block stays out of the plan body; print its one line after `Plan ready for review.`

3. Apply the result references from step 1 with `RESULT_KIND` = `plan`, `ARTIFACT_PATH` = the desloped `synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = the resolved pass count, `IN_PLAN_MODE` = true, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`.

4. Write the rendered plan to the plan file, then emit `Plan ready for review.`

5. After every pass, record it through the session agent (`update --completed-passes <N> --event pass_complete`).

---

## Phase 4: Multi-pass refinement

Skip when `passes` is 1. For pass N of 2 to `passes`, do not re-run the task. Target only unresolved conflicts from the prior adjudication, critic findings from the prior pass, and any dimension scored below 5 on any response, with this prompt:

> The following issues remain from the prior pass. Address ONLY these items:
>
> **Unresolved conflicts**: [from prior adjudication]
> **Critic findings**: [from prior critic.md]
> **Low-confidence areas**: [dimensions and responses scored below 5]
>
> For each item, give your resolution with evidence (file paths, line numbers, code references).

1. Create the pass (`pass-dir --session "<session_dir>" --pass <N>`) and write the prompt to `pass-<N>/prompt.md`, both through the session agent.
2. Dispatch as in Phase 2 with pass `<N>`. The Claude lane reads prior artifacts by path; external lanes get them inline.
3. Re-synthesize per Phase 3: re-score only affected dimensions and re-adjudicate only targeted disputes. Write `pass-<N>/synthesis.md`.
4. Stop early when no score moved by more than 1 and no new conflict appeared.
5. On the final pass, run Phase 3 steps 2 to 5 on `pass-<N>/synthesis.md`, adding a **Plan Evolution** section that says what was strengthened, corrected, or added across passes.

---

## Finish

Follow `ensemble-core.md` (Finish), through the session agent.

## Rules

- Do not modify project files, and never exit plan mode.
- Every plan step is one atomic commit.


## Portability notes

- `ask-user-choice` — follow the source's choice contract. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it. Honor a documented headless default when the source defines one; otherwise print a numbered list and wait for a numbered reply. Never invent a choice.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
