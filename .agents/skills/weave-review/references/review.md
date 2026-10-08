# Review results

Critic Findings states an additional verified issue or a rejected claim with
its deciding evidence. Omit it when the critic only improved wording or
repeated another section. Never narrate how the report was edited.

## Hero

`⚠ N blockers before merge` plus a one-liner per blocker; `✓ No blockers` when zero.

## Sections, in order

Scores · Verified Issues (Critical / Important / Suggestions) · False Positives Rejected · Reviewer Disagreements (only if any) · Critic Findings (only if any) · Confidence Evolution (only when PASS_COUNT > 1) · Summary · Attribution

Findings and Disagreements carry the consensus tags and ordering the caller recorded in its consensus map (`consensus 2/3`, `consensus 1/3 (uncontested)`; within a severity band: unanimous-verified, majority-verified, single-verified, then unverified). Omit tags when only one lane participated.
Put the tag on the finding's first bullet line, before any supporting test
cases or examples. Never detach it into its own paragraph after nested bullets.

## Example

```text
⚠ 1 blocker before merge
- src/retry.py: the backoff loop never stops on a permanent failure

## Scores
- maintainer 70/90, skeptic 63/90, builder 58/90

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

**Draft plan from findings** · **Fix now** (suggest the `weave-fix-review` skill) · **Done**

## Plan-brief extractor

List each verified finding as a fix step: file, change, test, commit message. Order by consensus then severity.
