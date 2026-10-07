---
name: weave-fix-review
description: >-
  Fix weave review findings — validate, add test coverage, fix, and commit
  each as atomic changes
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
metadata:
  source: "plugins/weave/skills/fix-review/SKILL.md"
---

# Fix Review Findings

Process weave code review findings from the conversation context. Validate each finding independently against the actual codebase and project conventions, add test coverage where applicable, apply fixes as separate atomic commits, and ensure all quality gates pass before each commit.

`<engine>` is `references/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`. It prints JSON; `"ok": false` carries the reason.

This command commits to a git repository, so it needs one with at least one commit. Without one, reply in one sentence that `fix-review` needs a git repository with commits, and stop.

---

## Orchestration Plan

Before executing any fixes, enter plan mode and produce a fix strategy from the review findings. Plan-mode activation varies by host:

- Claude Code: `EnterPlanMode` tool
- Cursor / Codex / Gemini: `/plan` or `Shift+Tab`

The plan must contain:

1. **Findings inventory**: each finding with its consensus level and severity
2. **Validity pre-assessment**: likely valid, likely incorrect, or needs investigation
3. **Fix ordering**: dependencies first, then highest consensus, then file proximity
4. **Test strategy per finding**: extend an existing test, add a case, or no test (and why)
5. **Risk assessment**: fixes that could break other code or conflict with each other
6. **Expected commit sequence**: the atomic commits this session will produce

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`). The user may adjust priorities, skip findings, or reorder the sequence. If plan mode is unavailable, write the plan as numbered steps in your response and continue.

---

## Phase 1: Parse and prioritize findings

Follow the approved plan for finding order; without one, use the default order below.

1. Locate the review report in the conversation context (output from the `weave-review` skill or similar).
2. Extract each finding into a numbered list with its consensus level (3, 2, or 1 reviewers), severity after consensus promotion (Critical / Important / Suggestion), reviewers, file and line, description, and recommendation.
3. Sort by priority:
   - Consensus Critical (3 reviewers)
   - Consensus Critical (2 reviewers, promoted)
   - Consensus Important (2 or 3 reviewers, promoted)
   - Single-reviewer Important
   - Single-reviewer Suggestions
4. Create a todo list tracking each finding.
5. Read the project's CLAUDE.md / AGENTS.md for conventions that apply to the fixes.

---

## Phase 2: Validate each finding

For each finding:

1. Read the exact lines the finding cites, the project's own APIs they use (signatures, return types, docstrings), and the conventions that apply.
2. Search for tests that already cover the code path.
3. Assess validity:
   - **Valid**: a real issue that aligns with project conventions
   - **Already addressed**: fixed in a later commit
   - **Incorrect**: the reviewer misread the code, or the suggestion would introduce a bug
   - **Out of scope**: valid but unrelated to this branch's changes
   - **Pre-existing**: valid but older than this branch
4. Record the verdict. For a valid finding, note the planned fix and test strategy. For any other verdict, cite the code, test, or convention that decides it.
5. Present each finding with its verdict, compared against the plan's predictions, and highlight changes. Wait for the user's confirmation before Phase 3. A pre-existing finding is fixed only when the user approves it. Without an interactive reply, stop here and report the verdicts: nothing is fixed or committed. A request that explicitly says to apply the fixes is that confirmation for the findings judged Valid, never for pre-existing ones and never for pushing.

---

## Phase 3: Apply fixes, one commit per finding

Process one finding at a time and finish its full cycle before the next. A finding that needs changes in several files is still one commit.

1. **Find existing tests.** Search the test directory for the affected function or module, read the test structure, and look for parameterized fixtures or helpers to extend.
2. **Write or extend a test**, following the project's test conventions strictly. Prefer, in order: a new entry in an existing parameterized fixture, a new case in an existing test function, a new test function in an existing file, and a new test file only when nothing covers the area.
3. **Apply the minimal fix** that addresses the finding, with no unrelated changes, following the project's conventions.
4. **Run the project's quality gates.** All must pass before committing. On a failure, adjust the fix, or update the test when the finding changes expected behavior.
5. **Commit** only the files changed for this finding, using the project's commit message format and a reference to the review finding. Write the message per `references/prose-rules.md`, with no `Co-Authored-By` line, no "Generated with" or other tool trailer, and no emoji; hosts add these by default, so strip them:

   ```console
   $ git add <specific-files>
   ```

6. **Verify clean state** with `git status`. No uncommitted changes may remain before the next finding.

### Recovery: quality gate failure

If a gate still fails after two attempts at the fix, revert the change with `git checkout -- <files>`, mark the finding "valid but could not apply cleanly", move to the next finding, and report it in the Phase 4 summary.

---

## Phase 4: Present results

Create the session directory:

```console
$ python3 <engine> init \
    --command fix-review \
    --bare
```

Write the session summary, with each finding, its verdict, and the commit that addressed it, to `<session_dir>/phase-4-summary.md` per `references/prose-rules.md`.

Read `references/present-results.md` and apply it with `RESULT_KIND` = `fix-review`, `ARTIFACT_PATH` = `<session_dir>/phase-4-summary.md`, `SESSION_DIR` = `<session_dir>`, `PASS_COUNT` = 1, `IN_PLAN_MODE` = false, `WORKER_BACKEND` = null, `PARTICIPANTS` = [], `EXECUTORS` = null, `MODELS` = null, `LABEL_MAP_PATH` = null.

After the reference returns, run the full quality gate one last time, show the commit log for the session, report the final pass/fail status, and mark the session complete:

```console
$ python3 <engine> update \
    --session "<session_dir>" \
    --status completed \
    --event session_complete \
    --link-latest
```

## Rules

- Never skip quality gates, bundle several findings into one commit, or modify code unrelated to the finding.
- Process consensus findings before single-reviewer findings.
- Use the project's commit message conventions from AGENTS.md / CLAUDE.md.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
