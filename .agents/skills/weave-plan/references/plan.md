# Plan results

Plan renders into the host's plan file, not chat. IN_PLAN_MODE is true, so there is no next-step panel.

Architecture Decision distinguishes required behavior from proposed defaults
and states the failure policy. Implementation Steps and Test Strategy enforce
that same contract; an unresolved requirement blocks its affected step.
Place units, scope and assumptions beside each estimate, and label a partial
estimate as partial.

Critic Findings states the risk, the chosen safeguard, and its place in the
final plan. It does not describe defects in earlier drafts or their repair.
Use "None." when no distinct risk remains to explain.

## Hero

`Plan: N steps, M files touched`

## Sections, in order

Architecture Decision · Implementation Steps · Test Strategy · Risks and Mitigations · Scores · Verification Summary · Adjudication · Critic Findings · Plan Evolution (only when PASS_COUNT > 1) · Attribution

## Example

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
- maintainer 68/90, skeptic 74/90, builder 61/90

## Verification Summary
- 12 of 14 claims verified.

## Adjudication
The skeptic's executor threading won over the builder's global flag.

## Critic Findings
- Quiet mode must stay silent; step 2 routes dry-run output through the verbosity check.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```
