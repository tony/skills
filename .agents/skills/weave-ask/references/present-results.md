# Weave present-results: shared rendering rules

Rules shared by every `/weave:*` result. The calling skill also loads one
file from `results/` for its `RESULT_KIND`: that file holds the hero, the body
sections in order, a literal example, the next-step options, and the plan-brief
extractor. Nothing else in `results/` is read.

## Contents

- Caller contract
- Render
- Output contract
- Attribution
- Next-step panel
- Plan-mode entry
- Failure modes

---

## Caller contract

The caller sets these variables before invoking this reference:

| Variable | Type | Purpose |
|---|---|---|
| RESULT_KIND | review, plan, ask, brainstorm, brainstorm-and-refine, refine, prompt, architecture, execute, fix-review, serene-bliss | Selects the `results/` file |
| ARTIFACT_PATH | absolute path | Desloped final artifact (single file); for `brainstorm`, the directory of per-participant outputs |
| SESSION_DIR | absolute path | Session directory for auxiliary writes |
| PASS_COUNT | integer | Toggles Evolution/Confidence sections |
| IN_PLAN_MODE | boolean | True for plan; suppresses the next-step panel |
| WORKER_BACKEND | `subagents`, `model-clis`, or null | Selects participant attribution; null for fix-review |
| PARTICIPANTS | JSON array of strings | Successful role IDs (`subagents`) or lane artifact IDs (`model-clis`) |
| EXECUTORS | JSON object or null | Participant ID to actual executor mapping; null for fix-review |
| MODELS | JSON array of strings or null | Resolved providers or models for `model-clis`; null otherwise |
| LABEL_MAP_PATH | absolute path or null | For Attribution; null when no label map exists |
| CASCADE_STATE | `early-exit`, `escalated`, or null | Set by cascade-capable callers (ask, review); null otherwise |

---

## Render

Read ARTIFACT_PATH (a single markdown file; a directory only for
`brainstorm`). Emit the kind file's hero (1-4 lines) from the artifact's
content, then its body sections in that exact order. Skip a section only
when its data is empty and the kind file marks it optional.

When only one participant produced output, the comparison never ran. Start
the hero with `Adversarial comparison unavailable: only <participant>
responded` and drop the winner or "best of N" claim; render the body
sections from that one output and list the failed participants with their
failure class in Attribution.

When CASCADE_STATE is `early-exit`, append `, cascade early-exit
(Maintainer lane only)` in subagent mode or `, cascade early-exit
(Claude lane only)` in model-CLI mode to the hero's first line.

---

## Output contract

1. The hero block comes first: 1-4 lines, no prose paragraphs. Nothing
   precedes it, including notes about what was or was not applied. The
   only exceptions are a nothing-applied or refused-stash opening from
   `mutating-run.md`: it replaces the hero, and the kind's hero line is then
   not rendered.
2. The body sections follow in the kind file's order with its level-2
   headings verbatim. Skip one only when its data is empty and the row is
   marked optional (`only when PASS_COUNT > 1`, `only if any`).
3. Add no sections and no heading outside the list: no title line, `Notes`,
   `Observations`, `What changed`, `Verified against X`, `Answering your N
   questions`, or `Confidence evolution` outside its slot. This holds when
   the input was inline text.
4. Plain bullets in every section, including content carried over from
   worker responses: `- Label: text` or a plain sentence, never
   `- **Label:** text`. Narrative paragraphs only inside `Adjudication`,
   `Reviewer Disagreements`, and `Critic Findings`. An artifact's own
   headings, bold sub-labels, and opening summary sentence do not carry into
   a slot: fold a sub-heading into the first words of its paragraph or
   bullet (`- Cursor: ...`), never a line of its own, and start the reply
   with the hero, never a sentence about what was run.
5. Never narrate how the run worked: no session files, `Bash`, interactive
   choices that were unavailable, stashes and worktrees that were cleaned up,
   or a deslop pass that changed nothing. The nothing-applied and
   refused-stash openings are the only text that may say what was not done.
   The deslop summary line, when the pass produced one, is the last line
   after Attribution.
6. Nothing follows Attribution except the deslop summary line: Attribution
   names the lanes and stops, and assumptions or caveats ("no codebase was
   checked", "confirm against your stack") appear once, at the start of the
   final result, never after it. No
   clustering, ranking, counting of distinct designs, or recommendation
   appears anywhere in the reply's own voice (brainstorm and
   brainstorm-and-refine originals included).
7. A run that stopped before producing the artifact (refused, failed, or
   declined) renders none of this: one sentence stating the result, then
   what the user needs to do next. No headings, bold labels, numbered
   menus, or local paths and temp files.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths. Each kind file carries its own example; values are invented. A stopped run, for any kind (serene-bliss shown), is a sentence and a plain list:

```text
Stopped before refining: serene-bliss needs a draft to improve and none was given.
- Paste the draft or give a file path, then run it again.
```

---

## Attribution

Render it as the final body section of every kind:

- If LABEL_MAP_PATH is set and the file exists: read the label map and show
  the blind-label to participant mapping.
- When WORKER_BACKEND is `subagents`, list the successful role IDs from
  PARTICIPANTS (`maintainer`, `skeptic`, `builder`) and state that they are
  host-native sub-agents. Show their executors from EXECUTORS. Do not claim
  model diversity. When the originals came from independent workers, say
  "generated independently in parallel" (for example "Host-native
  sub-agents, generated independently in parallel: maintainer, skeptic,
  builder").
- When WORKER_BACKEND is `model-clis`, list the successful lane artifact IDs
  from PARTICIPANTS (`claude`, `agy`, `gpt` as available), their actual
  executors from EXECUTORS, and resolved provider/model details from MODELS.
  The `gpt` lane normally runs through `codex`; do not call `gpt` a CLI.
- Name no local paths or temp files. Mention a file only when the user must
  act on it. Never say where outputs were saved, that saving was denied, or
  that condensed copies exist.

---

## Next-step panel

When IN_PLAN_MODE is true, skip this section. Otherwise call
`ask-user-choice` with the kind file's options in display order. When
CASCADE_STATE is `early-exit`, prepend **Escalate to full ensemble** as the
first option; on selection, return control to the caller's cascade
escalation path instead of Plan-mode entry.

Route the choice:

- **Done**: return. Session finalization is the caller's job.
- A text-suggestion option (Fix now, Refine, Brainstorm alternatives,
  Compare, Re-run): emit a one-line suggestion with the command name and
  return.
- A plan-entry option (any option that starts a plan): go to Plan-mode
  entry.

---

## Plan-mode entry

Only after the user picks a plan-entry option.

1. Launch one host-native sub-agent (in Claude Code, a Task sub-agent with
   `subagent_type: "general-purpose"` and `mode: "default"`). Input:
   ARTIFACT_PATH content plus the kind file's extractor instruction. Write
   its output to `<session_dir>/handoff/plan-brief.md`.
2. Call `EnterPlanMode`. If unavailable, emit this one line and stop:

   ```text
   Plan mode is unavailable here. Run weave-plan with the same task to plan this result.
   ```

3. In plan mode, read the brief and the codebase files it names, then write
   the plan file at the path the host's plan-mode message supplies, in the
   shape of the `weave-plan` skill Phase 3 step 3. Call `ExitPlanMode`.

---

## Failure modes

- ARTIFACT_PATH missing or empty: emit an error line; skip rendering and the panel.
- LABEL_MAP_PATH set but file missing: omit the label mapping and note "label map unavailable".
- `ask-user-choice` unavailable: skip the panel; end after Attribution.
- Host-native sub-agents unavailable for the plan brief: emit a plan-brief stub with the ARTIFACT_PATH pointer and take the `EnterPlanMode`-unavailable line.
- Plan-brief generation fails: emit an error; do not enter plan mode.
