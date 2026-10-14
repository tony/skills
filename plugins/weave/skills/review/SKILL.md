---
name: review
description: "Weave code review: run independent adversarial reviews in parallel, then synthesize findings"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Task", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"]
argument-hint: "[--cascade] [--passes=N] [--timeout=N|none] [--mode=fast|balanced|deep] [--no-deslop|--quiet-deslop|--verbose-deslop] [--workers=subagents|model-clis] [focus area]"
disable-model-invocation: true
---

# Weave Code Review

Run code review through independent adversarial workers in parallel, then synthesize findings into a report with evidence-backed adjudication.

The focus area comes from `$ARGUMENTS`; without one, review the whole branch.

`<engine>` is `../../scripts/engine.py` resolved from this skill's directory to an absolute path, written literally in every command, and run with `python3`.

## Worker selection

<!-- portable: ask-user-choice=headless-default -->

Before any other unresolved configuration choice or operational step, read
`../../references/worker-backends.md` (Caller contract). Resolve
`worker_backend` from `--workers=subagents|model-clis` using that reference;
if the flag is absent, ask its worker question first.
If interactive choice is unavailable, honor its documented headless default.

---

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Before dispatching reviewers, produce a review strategy.

Gather the facts read-only first:

```console
$ python3 <engine> context \
    --full-diff
```

It returns `repo`, `trunk`, `base`, `branch`, `commits` on the branch, and the diff stat and full diff in `markdown`. `base` is `origin/<trunk>` as last fetched, else the local trunk, so the comparison may be stale; say so in the plan. When `repo` is false there is nothing to review: reply in one sentence, with no local paths, that `review` needs a git repository with commits, add one line telling the user to run it from a project checkout, and stop. Read the project's CLAUDE.md / AGENTS.md as well.

The plan must contain:

1. **Branch summary**: what the branch does, from the commits and diff stats
2. **Review focus areas**: the highest-risk or most complex files and changes
3. **Relevant conventions**: the CLAUDE.md / AGENTS.md rules that bear on the changes
4. **Known concerns**: areas the user flagged, and risky patterns in the diff (large functions, missing tests, API changes)
5. **Prompt strategy**: what each reviewer's prompt should emphasize

Present the plan and wait for approval, then exit plan mode (`ExitPlanMode`). If plan mode is unavailable, write the plan as numbered steps in your response and continue; without an interactive way to approve, continue too. The session starts only after approval, because it creates persistent artifacts.

---

## Phase 1: Start the session

Follow `../../references/ensemble-core.md` (Start the session) with `--command review`. It asks each unresolved setting through `AskUserQuestion`.

Build the context packet per `ensemble-core.md` (Context packet), using the approved plan to choose what goes in. Run `context --full-diff` so external reviewers get the diff. Lead with conventions, the changed files with their diff stats, and key snippets of modified code. Known unknowns name the parts of the diff that are hard to review without more context.

---

## Phase 2: Cascade gate (only with `--cascade`)

Read `../../references/ensemble-techniques.md` (Technique 1) and apply it: run the Maintainer lane from Phase 3 alone, self-verify per Phase 4's Verify Claims step, and evaluate the five escalation triggers. For review, any **Critical** finding fires the judgment-call trigger, so Criticals always get ensemble confirmation. On **early-exit**, skip the other lanes, blind judging, and rubric scoring; run the Critic, then go to Phase 6 with `CASCADE_STATE` = `early-exit`. On **escalate** (or user escalation from the panel), continue to Phase 3 with the cheap-pass output reused as the Maintainer lane.

---

## Phase 3: Launch reviews in parallel

The shared worker prompt body is:

> <the focus from $ARGUMENTS, or: Review the changes on this branch for bugs, security issues, and convention violations.>
>
> Perform a thorough code review of the changes on this branch compared to <base>. The context packet holds the diff; run `git diff <base>...HEAD` for more. Read the CLAUDE.md or AGENTS.md at the repo root for project conventions.
>
> Review for:
> 1. **Bugs and logic errors**: incorrect behavior, edge cases, off-by-one errors
> 2. **Security issues**: injection, XSS, unsafe deserialization, secrets in code
> 3. **Project convention violations**: check against CLAUDE.md/AGENTS.md
> 4. **Code quality**: duplication, unclear naming, missing error handling
> 5. **Test coverage gaps**: new code paths without tests
>
> For each issue found, report:
> - Severity: Critical / Important / Suggestion
> - File and line: exact location
> - Description: what the issue is
> - Recommendation: how to fix it, with the evidence it rests on
>
> State only what the code you read shows. A value seen once (a delay, a limit) is not a rate or a guarantee. Behavior that depends on code or a contract you did not see (client defaults, server handling, idempotency) is unknown: say so, and make any recommendation that relies on it conditional.
>
> Report an issue only when it cites file:line and a reason another reviewer or the judge can check; drop any issue that cannot be checked.
>
> Use plain bullets with no bold.
>
> Length cap: at most 500 words in total, the highest-severity issues first, one short paragraph each, no code blocks beyond one-line quotes.

Follow `ensemble-core.md` (Dispatch lanes) with this body, substituting `base` from `context` for `<base>`, then (Close the repo guard). If only one reviewer responds, continue with it alone and say so.

---

## Phase 4: Synthesize findings

Apply `ensemble-core.md` (Blind judging, Synthesis protocol) and `../../references/consensus-map.md` to this pass's outputs. The convergence mode is **Merge**. Use this rubric in place of the default one:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Correctness | 3x | Real bugs found, no false positives |
| Specificity | 2x | Exact file/line, reproducible issue |
| Severity calibration | 2x | Critical is truly critical, not inflated |
| Actionability | 1x | Clear fix recommendations |
| Convention coverage | 1x | Checks project-specific rules from CLAUDE.md |

These weights are this plugin's own convention, like the default rubric.

Put these verification instructions in the judge's brief. Read the file and line of each reported issue to confirm it exists, check that a "Critical" has a real impact (exploitable or crash-worthy), and check each convention violation against the cited rule. A claim that rests on an unknown contract stays in Summary, not Verified Issues or the blocker count, and a recommendation that relies on it is conditional on it. A verified generic defect does not verify every example of it. Missing input validation is a defect only when a known contract forbids those inputs. When the project has no test runner, propose test behavior without choosing a framework.

### Deduplicate and calibrate severity

Group findings that refer to the same issue (same file, similar description). Each group carries its consensus tag and severity:

In `consensus.md`, record a short diagnostic quote from each reviewer counted for each finding. Match the issue, not just its file or remedy: a proposed parameter for backoff is not an independent finding that the whole policy needs configuration. Recheck the quotes and tags after splitting findings or accepting critic additions; new claims do not inherit the original finding's votes. Keep `consensus.md` to one line per finding.

- 1 reviewer: the reported severity.
- 2 or 3 reviewers: the highest severity any of them reported. Agreement shows in the consensus tag; it never raises severity.
- A finding is Critical only when verification confirmed the impact.

### Write the report

Read `../../references/present-results.md` and `../../references/results/review.md` before writing the report to `<session_dir>/pass-NNNN/synthesis.md` per `../../references/prose-rules.md`. If an agent writes it, give that agent these references too. Raw critic deltas stay in `critic.md`; integrate their verified substance into the owning report sections from the result template. With several reviewers, every finding bullet ends with its actual consensus tag, including Important and Suggestions; use the responding reviewer count as the denominator. With one reviewer, omit consensus tags. State the stale-base caveat in Summary; nothing sits between the hero and Scores. Do not render anything yet: results are presented once, in Phase 6, after the last pass.

---

## Phase 5: Multi-pass refinement

Skip when `passes` is 1. Read `../../references/ensemble-techniques.md` (Technique 2) for the residual ledger, and run the later passes as `ensemble-core.md` (Later passes) says. Only the ledger items are re-adjudicated.

The final pass's `synthesis.md` (pass 1 when `passes` is 1) feeds Phase 6. When `passes` > 1, it carries a **Confidence Evolution** section:

```markdown
## Confidence Evolution

| Finding | Pass 1 | Pass 2 | Pass 3 | Status |
|---------|--------|--------|--------|--------|
| file:42 null check | 2/3 reviewers | 3/3 reviewers | - | Confirmed |
| file:15 type error | 1/3 reviewers | 0/3 reviewers | - | Retracted |
| file:99 race condition | - | 2/3 reviewers | 3/3 reviewers | New (confirmed) |
```

---

## Phase 6: Polish and present

1. Unless `--no-deslop` was set, read `../../references/deslop-pass.md` and apply it once, with `ARTIFACT_PATH` set to the final pass's `synthesis.md`, `SESSION_DIR`, `BASELINE_SHA` set to `baseline_sha` from `init`, and `DESLOP_MODE` from the flags. Re-read `synthesis.md` for the desloped report; the deslop summary block follows the Attribution section.

2. Check the polished report against `verification.md` and the issue-matching
   quotes in `consensus.md`. Check every clause of each finding, including
   examples, impact and fixes, not only its headline. Move unsupported clauses
   to Summary or omit them; a later qualification does not repair an earlier
   absolute. Render settled disputes only in their owning result section.
   Keep the verified wording when presenting it.

3. Read `../../references/present-results.md` and `../../references/results/review.md`, and apply them with `RESULT_KIND` = `review`, `ARTIFACT_PATH` = the final `synthesis.md`, `SESSION_DIR`, `PASS_COUNT` = the resolved pass count, `IN_PLAN_MODE` = false, `LABEL_MAP_PATH` = `<session_dir>/pass-NNNN/label-map.json`, `CASCADE_STATE` = `early-exit`, `escalated`, or null without `--cascade`.

---

## Finish

Follow `ensemble-core.md` (Finish).

## Rules

- Run every available reviewer, even when one fails, and attribute each finding to the reviewers that found it.
- Consensus findings take priority over single-reviewer findings.
