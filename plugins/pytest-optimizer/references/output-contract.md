# Output contract

Every phase command prints its result in this fixed shape. Verbatim level-2
headings, declared order, no invented sections. This keeps four separate commands
feeling like one pipeline and makes the JSON memory legible at a glance.

## Shape

1. **Hero block** (1–4 lines, optional). A `⚠`/`✓` prefix or a one-line summary.
   No prose paragraphs. Examples:
   - `✓ scan complete — baseline 12.5s, noise band 0.45s, 7 hypotheses, 0 suite edits`
   - `⚠ 1 hypothesis dropped at the safety gate (xdist over shared SQLite)`
2. **Body sections** in the order each command declares (below). Skip a section
   only when it is genuinely empty, and say so in one line rather than inventing
   filler.
3. **Next-step panel** — an `AskUserQuestion` so the user can act without composing
   a follow-up command. Skip the panel only when the command is already running
   inside plan mode (where the plan itself is the decision point). Without an
   interactive question tool, list the options as text and take the stated
   non-interactive default.

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
- `## Hypotheses` — candidate table: id, heuristic, evidence, prior
  risk/effort.

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
