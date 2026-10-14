# Output contract

Every phase command prints its result in this fixed shape: verbatim level-2
headings, declared order, no invented sections.

## Contents

- Shape
- What a reply may claim
- Halted run
- Per-command body sections

## Shape

1. **Hero block** (1-4 lines, required on every reply that has sections): a `⚠`/`✓`
   prefix or a one-line summary, no prose paragraphs.
2. **Body sections** in the order each command declares (below). Print a section
   that is empty as "None."; omit `## Applied` or `## Skipped` of `03-execute` when it has no items. Place a candidate under the section its measurement earned (a count drop is `## Rejected`), and advise nothing the runs did not measure.
3. **Next-step panel**: an `AskUserQuestion` so the user can act without composing
   a follow-up command. Skip it inside plan mode, where the plan is the decision
   point. Without an interactive question tool, print the options as a plain list and
   stop.

After the last section, add at most one closing sentence in plain words for
anything the user must know that has no section (a stale baseline, a lowered run
count, an unrecorded approval, files the timed runs wrote). In `03-execute` that
sentence is the merge command for the result branch. It comes before the
next-step panel and, with no question tool, is the whole next step. Name no
state field, file, sandbox detail, or whether plan mode is available, and never
open it with a label such as "Next step:" or a leading "Also,". State what
happened, never a list of what did not (no "neither", "no X and no Y"). Say
nothing about pushing: no "only in your local repo", no push command.

Name every heuristic in words with its id, never the id alone. Name a path or
temp file only when the user must act on it; refer to the memory directory and
the repo by role. Between the hero and the first heading there is no prose: put
an approval note in the hero line or the closing sentence.

Reply as plain text outside any code fence, with plain bullets, no bold (never
`- **Label:** ...`), and no local paths. Each phase skill carries an example
reply in this shape; the rules here apply to all of them.

`## Hypotheses` lists only detectors that become entries; the measurement
heuristics (H01-H07) and the safety gates (H17, H18) appear in the other
sections.

A `01-benchmark` reply with no candidate that touched order, scope, or
parallelism omits `## Safety-gate results` and says nothing about gates.

A deselecting item (H15, H37) says "removes N tests from the default run" in its
`## Ranked plan` bullet, so the user sees the count at the approval gate. With
several items the hero counts commits only, and each bullet gives its own
saving measured alone.

A plan with one commit omits `## Ordering rationale`.

Without plan mode, the same reply is the whole message: the hero line carries the
approval request, and nothing precedes it or follows the last section.

A deselecting item changes the `## Result` bullet of `03-execute` to "the default run shrank from 42 to
40 tests and takes 7.9s against 12.5s".

## What a reply may claim

State only what a command printed or a file showed in this run.

- Time is recovered only after `03-execute` measures it. Before that, say
  "measured alone" for a benchmark and "projected" for a plan. Never add the
  savings of several items together.
- A deselecting item (H15, H37) saves time by running fewer tests: say the
  default run shrinks from N to M tests. A change that keeps every test is a
  faster suite: say the same N tests ran. Never use one phrase for both.
- Time no run attributed is unattributed. Do not call it startup, collection or
  anything the suite cannot reduce.
- Name the project command that failed or was missing ("the project's test
  command cannot start"), not what is absent from every environment. Do not
  suggest installing pytest or changing the runner.
- A threshold, limit or minimum seen only in a stand-in runner is a fact about
  that runner. Offer no further change (a smaller sleep, another threshold) that
  no run measured.
- A failed verification is reported as the printed result (counts and exit
  status). Give no cause, and no threshold read from the runner's source.
- Counts and node ids show which tests ran, not that their assertions are
  unchanged.

## Halted run

When a phase stops before its work (missing input, dirty tree, plan hash
mismatch, no suite), print one result sentence naming what stopped it, then one
sentence on what the user must do. Give one reason only, the first check that
failed, as a single clause naming the missing prerequisite (never a list of what is
absent, and never "or" between two causes); leave out sandbox, placeholder-file, and
cleanup-risk detail. No body sections, no panel, no bold, no
projected timings or results. When the user pasted durations or named a
likely cause, add one sentence saying where the pasted time sits (setup versus
call, which fixture) as a hypothesis to benchmark; never what a change would save,
and never call a scope change or any other change a fix or a likely fix.

```text
I stopped before measuring because this directory has no pytest suite.
Run the skill from the project root that holds the tests, or send the path to it.
```

With pasted durations, insert one sentence after the first: "Your durations put
most of the time in db_session setup, which is a hypothesis to benchmark once the
suite is available."


Without a prior phase, the same two sentences name the missing phase's output
in words, not by file:

```text
I stopped before planning because no benchmarks have been recorded.
Run 01-benchmark first, then run this phase again.
```

The same shape for the other phases, each naming one missing output:

```text
I stopped before benchmarking because no baseline has been recorded.
Run 00-scan first, then run this phase again.
```

```text
I stopped before applying because no plan has been recorded.
Run 02-plan first, then run this phase again.
```

## Per-command body sections

**`00-scan`**

- `## Environment` — pytest + plugin versions, gated-off capabilities, resolved
  test command, memory dir.
- `## Baseline` — median wall-time, noise band, trust floor, and the unattributed
  share when profiling leaves one.
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
  outcomes for each candidate that needed them. A scope, order, or parallelism
  change needs both. Omit the section when no candidate did.

**`02-plan`**

- `## Ranked plan` — ordered commits (only items whose target file exists at `HEAD` or is created by the item; the hero counts only these) with score breakdown, target files, draft
  subject (in the same sentence, no `Draft subject:` label), verify command.
  A hygiene item says it is a hygiene item with no timing.
- `## Dropped at the gate` — candidates below `safety 0.4` or `impact 0`, and items whose target file is absent at `HEAD`, with the
  prerequisite refactor surfaced separately. Name a refactor only for an item that
  has one; never state that an item needs none.
- `## Ordering rationale` — why safety-gate fixes and typings precede scope and
  parallelism, in one line. Omit the section when the plan has one commit.

**`03-execute`**

- `## Applied` — per item: commit SHA, subject, verify result. Omitted when nothing was applied.
- `## Skipped` — per item: why it was discarded in the scratch worktree (failed verify, patch no longer applies, files outside the plan). Omitted when nothing was skipped.
- `## Result` — post-suite wall-time against the control (the same checkout without the changes), how much faster, and the test-count statement for the item kind.

The closing sentence is the merge command; the reply carries no remark about
commit trailers or what the host adds.
