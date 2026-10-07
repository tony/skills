# Review results

## Hero

`⚠ N blockers before merge` plus a one-liner per blocker; `✓ No blockers` when zero.

## Sections, in order

Scores · Verified Issues (Critical / Important / Suggestions) · False Positives Rejected · Reviewer Disagreements · Critic Findings · Confidence Evolution (only when PASS_COUNT > 1) · Summary · Attribution

Findings and Disagreements carry the consensus tags and ordering the caller recorded in its consensus map (`consensus 2/3`, `consensus 1/3 (uncontested)`; within a severity band: unanimous-verified, majority-verified, single-verified, then unverified). Omit tags when only one lane participated.

## Example

```text
⚠ 1 blocker before merge
- src/retry.py: the backoff loop never stops on a permanent failure

## Scores
- maintainer 31/40, skeptic 28/40, builder 26/40

## Verified Issues
### Critical
- src/retry.py: unbounded retry on a 4xx response (consensus 3/3)
### Important
- src/queue.py: a failed requeue is logged but not counted (consensus 2/3)
### Suggestions
- Name the retry limit instead of using 5 inline (consensus 1/3 (uncontested))

## False Positives Rejected
- A claimed race in the worker pool: the lock is held across the check.

## Summary
One blocker; the other findings are local fixes.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

## Next-step options

**Draft plan from findings** · **Fix now** (suggest `/weave:fix-review`) · **Done**

## Plan-brief extractor

List each verified finding as a fix step: file, change, test, commit message. Order by consensus then severity.
