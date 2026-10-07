# Output contract

Every phase command prints its result in this fixed shape: verbatim level-2
headings, declared order, no invented sections.

## Contents

- Shape
- Halted run
- Per-command body sections

## Shape

1. **Hero block** (1-4 lines, optional): a `⚠`/`✓` prefix or a one-line summary,
   no prose paragraphs.
2. **Body sections** in the order each command declares (below). Skip a section
   only when it is empty, and say so in one line.
3. **Next-step panel**: an `AskUserQuestion` so the user can act without composing
   a follow-up command. Skip it inside plan mode, where the plan is the decision
   point. Without an interactive question tool, list the options as text and take
   the stated non-interactive default.

Name every heuristic in words with its id, never the id alone. Name a path or
temp file only when the user must act on it; refer to the memory directory and
the repo by role. Between the hero and the first heading there is no prose: put
a plan-mode or approval note in the hero line or the closing line.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`). A `00-scan` reply:

```text
✓ scan complete: baseline 12.5s, noise band 0.45s, 2 hypotheses

## Environment

- pytest 8.3.2 with xdist 3.6.1; deadfixtures not installed, so its check is skipped.

## Baseline

- Median 12.5s over 5 runs; trust floor 50ms.

## Slowest tests

- test_export_large spends 0.61s in one call (H01 slow test body).

## Slowest fixtures

- db_session setup runs 3 times at 4.8s each; the cost is billed to the first test (H03 shared-scope attribution).

## Hypotheses

- H10 mis-scoped fixture: widen db_session to session scope, 4.8s of setup repeated per test.
- H01 slow test body: test_export_large spends 0.61s in one call.
```

A `01-benchmark` reply:

```text
✓ 1 validated, 1 rejected

## Validated

- H10 mis-scoped fixture: db_session to session scope saves 4.6s, above the 0.45s band, confidence 0.9.

## Rejected

- H01 slow test body: test_export_large saves 0.02s, inside the noise band.

## Safety-gate results

- Order independence held across 3 seeds; collection is deterministic.
```

A `02-plan` reply:

```text
✓ 1 commit planned, 2.7s of the 12.5s baseline recovered; reply "approve" to record the plan, or name items to drop or reorder

## Ranked plan

- 1. H10 mis-scoped fixture: widen make_config to session scope in tests/conftest.py, total score 0.87, saves 2.7s above the 0.45s band, verified with pytest expecting 40 of 40 passing.
  Draft subject: tests(fixtures) Widen make_config to session scope

## Dropped at the gate

- H33 fixed sleep in test_report: saves 0.03s, inside the noise band, so impact is 0.

## Ordering rationale

- One commit, so there is nothing to order.
```

A `03-execute` reply:

```text
✓ 1 applied, 1 skipped

## Applied

- 7c1e9d4 Share db_session across the session, verify green, 12.5s to 7.9s.

## Result

- 7.9s against a 12.5s baseline, 4.6s recovered.
```

## Halted run

When a phase stops before its work (missing input, dirty tree, plan hash
mismatch, no suite), print one result sentence naming what stopped it, then one
sentence on what the user must do. No body sections, no panel, no bold, no
projected timings or results. When the user pasted durations or named a
likely cause, add one sentence saying where the pasted time sits (setup versus
call, which fixture) as a hypothesis to benchmark; never what a change would save.

```text
I stopped before measuring because this directory has no pytest suite.
Run the skill from the project root that holds the tests, or send the path to it.
```

With pasted durations, insert one sentence after the first: "Your durations put
most of the time in db_session setup, which is a hypothesis to benchmark once the
suite is available."


## Per-command body sections

**`00-scan`**

- `## Environment` — pytest + plugin versions, gated-off capabilities, resolved
  test command, memory dir.
- `## Baseline` — median wall-time, noise band, trust floor.
- `## Slowest tests` — top `call` rows with root-cause notes.
- `## Slowest fixtures` — top `setup`/`teardown` rows; note shared-scope
  attribution.
- `## Hypotheses` — candidates as bullets: heuristic id and name, evidence,
  prior risk/effort.

**`01-benchmark`**

- `## Validated` — candidates whose measured delta cleared the noise band and
  passed the gates (id, median delta, confidence).
- `## Rejected` — within-noise or gate-failing candidates, each with the reason.
- `## Safety-gate results` — order-independence and collection-determinism
  outcomes.

**`02-plan`**

- `## Ranked plan` — ordered commits with score breakdown, target files, draft
  subject, verify command.
- `## Dropped at the gate` — candidates below `safety 0.4` or `impact 0`, with the
  prerequisite refactor surfaced separately.
- `## Ordering rationale` — why safety-gate fixes and typings precede scope and
  parallelism; one line, and "nothing to order" when the plan has one commit.

**`03-execute`**

- `## Applied` — per item: commit SHA, measured verify result.
- `## Skipped` — per item: revert reason (failed green-verify, conflict).
- `## Result` — post-suite wall-time vs `baseline.json`, total recovered.
