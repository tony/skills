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
3. **Next-step panel**: an `ask-user-choice` so the user can act without composing
   a follow-up command. Skip it inside plan mode, where the plan is the decision
   point. Without an interactive question tool, list the options as text and take
   the stated non-interactive default.

Name every heuristic in words with its id, never the id alone.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`). A `00-scan` reply:

```text
✓ scan complete: baseline 12.5s, noise band 0.45s, 2 hypotheses

## Environment

- pytest 8.3.2 with xdist 3.6.1; deadfixtures not installed, so its check is skipped.

## Baseline

- Median 12.5s over 5 runs; trust floor 50ms.

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
sentence on what the user must do. No body sections, no panel, no projected
timings or results.

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
  parallelism.

**`03-execute`**

- `## Applied` — per item: commit SHA, measured verify result.
- `## Skipped` — per item: revert reason (failed green-verify, conflict).
- `## Result` — post-suite wall-time vs `baseline.json`, total recovered.
