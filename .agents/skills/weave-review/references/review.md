# Review results

Each claim has one home, whether it came from a reviewer or the critic:

- Verified Issues owns verified defects, their supported impact and fixes
  whose preconditions are established.
- False Positives Rejected owns claims contradicted by deciding evidence.
- Reviewer Disagreements owns unsettled reviewer disputes with both sides'
  evidence.
- Summary owns each unknown contract, explained once, and the check that
  settles it.

A finding that touches an unknown contract names it in a clause and does not
restate Summary's explanation. When its fix depends on that contract, the
fix sentence itself carries the condition; a caveat in Summary does not make
the finding's fix unconditional.

A critic's point goes into the finding, rejection or unresolved check it
belongs to. Label no item by who raised it ("critic addition", "skeptic
only"); consensus tags carry the vote counts. A proposal left unused because
a contract is unknown is not a disproved claim. Keep raw critic deltas in
`critic.md`; render the final evidence and recommendation, not the sequence
of proposed and rejected report edits.

## Hero

`⚠ N blockers before merge` plus a one-liner per blocker; `✓ No blockers` when zero.

## Sections, in order

Scores · Verified Issues (Critical / Important / Suggestions) · False Positives Rejected · Reviewer Disagreements (only if any) · Confidence Evolution (only when PASS_COUNT > 1) · Summary · Attribution

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
