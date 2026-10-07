# Ask results

## Hero

One-sentence answer.

## Sections, in order

Verified Answer · Evidence (file:line bullets) · Disagreements (only if any) · Refinement Notes (only when PASS_COUNT > 1) · Attribution

Disagreements carry the consensus tags the caller recorded (`consensus 2/3`); omit them when only one lane participated.

## Example

```text
Retries stop after 5 attempts; the 6th failure marks the job dead.

## Verified Answer
The handler re-queues only on 5xx responses and caps attempts in `MAX_ATTEMPTS`.

## Evidence
- src/retry.py:41 compares the attempt count with `MAX_ATTEMPTS`.
- src/queue.py:88 requeues only when `retryable(status)` is true.

## Disagreements
- The skeptic read the cap as 3. The constant is 5, so that reading was dropped.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

## Next-step options

**Turn this into a plan** · **Refine the answer** (suggest `/weave:refine`) · **Done**

## Plan-brief extractor

Treat the answer as a task. List the implementation steps required to act on it.
