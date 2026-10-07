# Plan results

Plan renders into the host's plan file, not chat. IN_PLAN_MODE is true, so there is no next-step panel.

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
