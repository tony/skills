# Weave present-results: unified output rendering and next-step panel

A shared rendering layer for all `/weave:*` commands. Consolidates
output presentation into one place: a hero block, prescribed body
sections per result kind, an attribution footer, and an interactive
next-step panel with active plan-mode handoff.

## Contents

- Caller contract
- Phase A: Render output (Steps 1-4, with a literal example per result kind)
- Phase B: Next-step panel
- Phase C: Active plan-mode entry
- Failure modes

---

## Caller contract

The caller sets these variables before invoking this reference:

| Variable | Type | Purpose |
|---|---|---|
| RESULT_KIND | one of: review, plan, ask, brainstorm, brainstorm-and-refine, refine, prompt, architecture, execute, fix-review, serene-bliss | Selects template and handoff options |
| ARTIFACT_PATH | absolute path | Desloped final artifact (single file); for `brainstorm`, the directory of per-participant outputs |
| SESSION_DIR | absolute path | Session directory for auxiliary writes |
| PASS_COUNT | integer | Toggles Evolution/Confidence sections |
| IN_PLAN_MODE | boolean | True for plan; suppresses next-step panel |
| WORKER_BACKEND | `subagents`, `model-clis`, or null | Selects participant attribution; null for fix-review |
| PARTICIPANTS | JSON array of strings | Successful role IDs (`subagents`) or lane artifact IDs (`model-clis`) |
| EXECUTORS | JSON object or null | Participant ID to actual executor mapping; null for fix-review |
| MODELS | JSON array of strings or null | Resolved providers or models for `model-clis`; null otherwise |
| LABEL_MAP_PATH | absolute path or null | For Attribution; null when no label map exists |
| CASCADE_STATE | `early-exit`, `escalated`, or null | Set by cascade-capable callers (ask, review); null otherwise |

---

## Phase A: Render output

### Step 1: Read the artifact

- When RESULT_KIND is `brainstorm`: ARTIFACT_PATH is a **directory**. List
  its contents to find per-participant output files.
- All other RESULT_KINDs (`prompt` included): ARTIFACT_PATH is a **single
  markdown file**. Read it.

### Step 2: Compose the hero block

Look up RESULT_KIND in this table. Fill placeholders from the artifact
content. Emit 1–4 lines.

| RESULT_KIND | Hero shape |
|---|---|
| review | `⚠ N blockers before merge` + per-blocker one-liner; `✓ No blockers` when zero |
| plan | `Plan: N steps, M files touched` |
| ask | One-sentence answer |
| brainstorm | `N ideas from M participants` |
| brainstorm-and-refine, refine, serene-bliss | `Refined through N passes` (suffix `(early-stop @ K)` if converged early) |
| prompt | `Winner: <participant>` |
| architecture | `Architecture: <chosen approach>` |
| execute | `Best of N implementations` |
| fix-review | `N fixes applied, M skipped` |

When only one participant produced output, the comparison never ran. Start
the hero with `Adversarial comparison unavailable: only <participant>
responded` and drop the winner or "best of N" claim; render the body
sections from that one output and list the failed participants with their
failure class in Attribution.

When CASCADE_STATE is `early-exit`, append `, cascade early-exit
(Maintainer lane only)` in subagent mode or `, cascade early-exit
(Claude lane only)` in model-CLI mode to the hero's first line.

### Step 3: Render body sections

Look up RESULT_KIND in this table. Render sections **in this exact
order** using the artifact content. Skip a section only when its
condition is false or its data is empty AND the section is marked
optional.

| RESULT_KIND | Body sections (in this exact order) |
|---|---|
| review | Scores · Verified Issues (Critical / Important / Suggestions) · False Positives Rejected · Reviewer Disagreements · Critic Findings · Confidence Evolution (only when PASS_COUNT > 1) · Summary · Attribution |
| plan | Architecture Decision · Implementation Steps · Test Strategy · Risks and Mitigations · Scores · Verification Summary · Adjudication · Critic Findings · Plan Evolution (only when PASS_COUNT > 1) · Attribution. Rendered into the harness plan file, not chat. |
| ask | Verified Answer · Evidence (file:line bullets) · Disagreements (only if any) · Refinement Notes (only when PASS_COUNT > 1) · Attribution |
| brainstorm | Per-participant responses (variants flattened) · Attribution. List each participant's ideas as written; do not cluster, rank, tabulate, or recommend. |
| brainstorm-and-refine, refine, serene-bliss | Final Result · Evolution Summary · Rationale Chain · Attribution |
| prompt | Per-variant outputs · Winner Selection Rationale · Attribution |
| architecture | Chosen Architecture · Component Map · Trade-off Analysis · Risks · Attribution |
| execute | Winning Implementation · Diff Summary · Trade-offs · Attribution |
| fix-review | Applied Fixes · Tests Added · Skipped Findings · Final Verification · Attribution |

For `execute`, Winning Implementation is one bullet per file with the
participant it came from; never paste file contents.

For `review` and `ask`, findings and Disagreements carry the consensus
tags and ordering the caller recorded in its consensus map
(`consensus 2/3`, `consensus 1/3 (uncontested)`; for `review`, within
a severity band: unanimous-verified, majority-verified,
single-verified, then unverified). Omit consensus tags when only one lane participated.

### Output contract

> **OUTPUT CONTRACT.** Render exactly:
>
> 1. The hero block. 1–4 lines maximum. No prose paragraphs in the hero.
> 2. The body sections above, in the listed order, with the listed
>    level-2 headings verbatim. Skip a section only when its data is
>    empty *and* the row is marked optional (`only when PASS_COUNT > 1`,
>    `only if any`).
> 3. No invented sections. Do not add `Verified against X`, `Answering
>    your N questions`, `Notes`, `Observations`, `Confidence evolution`
>    outside the prescribed slot, or any other heading not in the section
>    table.
> 4. Prefer tables and tight bullets. Narrative paragraphs are allowed
>    only inside `Adjudication` / `Reviewer Disagreements` and
>    `Critic Findings`. Use plain bullets in every section, including
>    content carried over from worker responses: write `- Label: text`
>    or a plain sentence, never `- **Label:** text`.
> 5. A run that stopped before producing the artifact (refused, failed, or
>    declined) renders none of this: one sentence stating the result, then
>    what the user needs to do next. No headings, bold labels, numbered
>    menus, or local paths.
> 6. The deslop summary line, when the pass produced one, is the last line
>    after Attribution. Nothing precedes the hero, including notes about
>    what was or was not applied.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths. Each kind below follows its own section list; values are invented:

A stopped run, for any kind (serene-bliss shown), is a sentence and a plain list:

```text
Stopped before refining: serene-bliss needs a draft to improve and none was given.
- Paste the draft or give a file path, then run it again.
```

Refine, brainstorm-and-refine, and serene-bliss:

```text
Refined through 2 passes

## Final Result
Retry delivery with exponential backoff, capped at 5 attempts.

## Evolution Summary
- Pass 1 picked the maintainer draft (34/40).
- Pass 2 merged the skeptic's cap on attempts.

## Rationale Chain
- Backoff avoids hammering a failing endpoint.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Review:

```text
⚠ 1 blocker before merge
- src/retry.py: the backoff loop never stops on a permanent failure

## Scores
- maintainer 31/40, skeptic 28/40, builder 26/40

## Verified Issues
### Critical
- src/retry.py: unbounded retry on a 4xx response (consensus 3/3)
### Important
- src/queue.py: a failed requeue is logged but not counted (consensus 2/3)
### Suggestions
- Name the retry limit instead of using 5 inline (consensus 1/3 (uncontested))

## False Positives Rejected
- A claimed race in the worker pool: the lock is held across the check.

## Summary
One blocker; the other findings are local fixes.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Ask:

```text
Retries stop after 5 attempts; the 6th failure marks the job dead.

## Verified Answer
The handler re-queues only on 5xx responses and caps attempts in `MAX_ATTEMPTS`.

## Evidence
- src/retry.py:41 compares the attempt count with `MAX_ATTEMPTS`.
- src/queue.py:88 requeues only when `retryable(status)` is true.

## Disagreements
- The skeptic read the cap as 3. The constant is 5, so that reading was dropped.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Brainstorm:

```text
9 ideas from 3 participants

## Per-participant responses
### maintainer
- Cache the parsed config per process.
- Add a `doctor` subcommand.
### skeptic
- Drop the plugin hook; it has one caller.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Prompt:

```text
Winner: skeptic

## Per-variant outputs
- maintainer 24/40: adds the flag but skips the empty-input case.
- skeptic 33/40: adds the flag, handles empty input, and extends the test.
- builder: unavailable (timeout).

## Winner Selection Rationale
- The skeptic is the only implementation that passes every quality gate.

## Attribution
Host-native sub-agents: maintainer, skeptic. The builder timed out.
```

Architecture:

```text
Architecture: one engine module with thin CLI wrappers

## Chosen Architecture
A single `engine` module owns state; each command is a wrapper.

## Component Map
- engine.py: sessions and guards
- skills/: one prose workflow per command

## Trade-off Analysis
- One module is simple to test; it grows with every command.

## Risks
- The engine becomes a catch-all if wrappers start owning logic.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Execute, after the user's stash is restored:

```text
Best of 3 implementations

## Winning Implementation
- src/cli.py from skeptic; tests/test_cli.py from builder.

## Diff Summary
- Adds --dry-run to the CLI and one test for it.

## Trade-offs
- The skeptic's parser is stricter and rejects an empty target.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Execute when nothing was applied (no way to confirm); prompt and architecture open the same way over their own sections:

```text
Nothing applied: confirmation was unavailable, so your checkout is unchanged.
- Best of 3 implementations: src/cli.py from skeptic, tests/test_cli.py from builder.
- Re-run and confirm the plan to apply it.

## Winning Implementation
- src/cli.py from skeptic; tests/test_cli.py from builder.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

Execute with a refused stash restore: put this before the hero, then the same shape.

```text
Your uncommitted changes are safe in a stash (3f2a9c1) and were not restored.
- Overlap: src/cli.py
- Inspect it: git stash show --patch 3f2a9c1
- Recover: run the commands below one at a time.
```

Fix-review:

```text
2 fixes applied, 1 skipped

## Applied Fixes
- Bound the retry loop (commit a1b2c3d).
- Count failed requeues (commit d4e5f6a).

## Tests Added
- test_retry_stops_on_4xx extends the parametrized retry cases.

## Skipped Findings
- Rename the constant: the file has your uncommitted edits.

## Final Verification
- Formatter, linter, and tests pass.

## Attribution
Findings came from the weave review in this conversation.
```

Plan renders into the host's plan file, not chat:

```text
Plan: 4 steps, 3 files touched

## Architecture Decision
Add the flag in the parser and thread it to the executor.

## Implementation Steps
1. Parse `--dry-run` in src/cli.py.
2. Print planned actions in src/runner.py.

## Test Strategy
- Extend the CLI parser test with a dry-run case.

## Risks and Mitigations
- A side effect outside the runner would still execute; grep for direct calls.

## Scores
- maintainer 30/40, skeptic 33/40, builder 27/40

## Verification Summary
- 12 of 14 claims verified.

## Adjudication
The skeptic's executor threading won over the builder's global flag.

## Critic Findings
- Step 2 omitted the quiet-mode path; added.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

### Step 4: Render Attribution

Shared across all RESULT_KINDs. Render as the final body section:

- If LABEL_MAP_PATH is set and file exists: read the label map and show
  the blind-label → participant mapping.
- When WORKER_BACKEND is `subagents`, list the successful role IDs from
  PARTICIPANTS (`maintainer`, `skeptic`, `builder`) and state that they are
  host-native sub-agents. Show their executors from EXECUTORS. Do not claim
  model diversity.
- When WORKER_BACKEND is `model-clis`, list the successful lane artifact IDs
  from PARTICIPANTS (`claude`, `agy`, `gpt` as available), their actual
  executors from EXECUTORS, and resolved provider/model details from MODELS.
  The `gpt` lane normally runs through `codex`; do not call `gpt` a CLI.
- Name no local paths or temp files. Mention a file only when the user must
  act on it. Never say where outputs were saved, that saving was denied, or
  that condensed copies exist.

---

## Phase B: Next-step panel

When IN_PLAN_MODE is true, skip Phase B entirely.

### Step 1: Present options

Call `ask-user-choice` with options from this table. When CASCADE_STATE
is `early-exit`, prepend **Escalate to full ensemble** as the first
option; on selection, return control to the caller's cascade escalation
path instead of Phase C.

| RESULT_KIND | Options (in display order) |
|---|---|
| review | **Draft plan from findings** · **Fix now** (suggest the `weave-fix-review` skill) · **Done** |
| ask | **Turn this into a plan** · **Refine the answer** (suggest the `weave-refine` skill) · **Done** |
| brainstorm | **Pick one and plan it** (sub-prompt for which idea, then plan) · **Refine further** (suggest the `weave-refine` skill) · **Done** |
| brainstorm-and-refine, refine, serene-bliss | **Plan the refined result** · **Refine again** (suggest the `weave-refine` skill) · **Done** |
| architecture | **Plan the chosen architecture** · **Brainstorm alternatives** (suggest the `weave-brainstorm` skill) · **Done** |
| execute | **Compare with another participant** (suggest the `weave-prompt` skill) · **Done** |
| prompt | **Use the winner - plan it** · **Re-run with different variants** · **Done** |
| fix-review | **Review the branch again** (suggest this skill) · **Done** |

### Step 2: Route user choice

- **Done** → return. Session finalization is the caller's
  responsibility.
- Text-suggestion options (Fix now, Refine, Brainstorm alternatives,
  Compare, Re-run) → emit a one-line suggestion with the command name
  and return.
- **Plan-entry options** (Draft plan, Turn into plan, Plan the refined
  result, Plan the chosen architecture, Pick one and plan it, Use the
  winner - plan it) → proceed to
  Phase C.

---

## Phase C: Active plan-mode entry

Triggered only when the user picks a plan-entry option in Phase B.

### Step 1: Synthesize plan brief

Launch one host-native sub-agent. In Claude Code, use a Task sub-agent
with `subagent_type: "general-purpose"` and `mode: "default"`. Input:
ARTIFACT_PATH content plus the extractor instruction from this table.
Write its output to `<session_dir>/handoff/plan-brief.md`.

| RESULT_KIND | Extractor instruction |
|---|---|
| review | List each verified finding as a fix step: file, change, test, commit message. Order by consensus then severity. |
| ask | Treat the answer as a task. List the implementation steps required to act on it. |
| brainstorm | Treat the user-selected idea as a task. List the implementation steps. |
| brainstorm-and-refine / refine / serene-bliss | Treat the refined artifact as a task. List the implementation steps. |
| architecture | Decompose the chosen architecture into ordered build steps: file, change, dependencies, tests. |
| execute / prompt | Convert the winning implementation / output into apply-as-PR steps: file, diff, test, commit. |

### Step 2: Enter plan mode

Call `EnterPlanMode`. If unavailable, go to headless fallback.

### Step 3: Write plan file

In plan mode: read `<session_dir>/handoff/plan-brief.md`, read the
codebase files referenced in the brief, write the plan file at the path
supplied by the host's plan-mode system message. Format as an
Implementation Plan (same shape as the `weave-plan` skill Phase 3 step 3). Call
`ExitPlanMode`.

### Headless fallback

If `EnterPlanMode` is unavailable, emit one line and stop:

```
Plan mode is unavailable here. Run weave-plan with the same task to plan this result.
```

---

## Failure modes

| Mode | Behaviour |
|---|---|
| ARTIFACT_PATH missing or empty | Emit error line; skip rendering, skip panel. |
| LABEL_MAP_PATH set but file missing | Omit label mapping from Attribution; note "label map unavailable". |
| ask-user-choice unavailable | Skip Phase B; end after the Attribution section. |
| EnterPlanMode unavailable | Headless fallback (Phase C). |
| Host-native sub-agents unavailable (Phase C Step 1) | Emit plan-brief stub with ARTIFACT_PATH pointer; proceed to headless fallback. |
| Plan-brief generation fails | Emit error; do not enter plan mode. |
