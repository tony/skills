# Plan results

Plan renders into the host's plan file, not chat. IN_PLAN_MODE is true, so there is no next-step panel.

State the plan's final decisions in every section, never how drafts changed: no "restored", "recounted", "added", or "removed" about the plan itself. Critic Findings lists what the critic found wrong, each with where the plan now covers it.

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
- The quiet-mode path had no step; step 2 now covers it.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```
