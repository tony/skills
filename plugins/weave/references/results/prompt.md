# Prompt results

## Hero

`Winner: <participant>`

## Sections, in order

Per-variant outputs · Winner Selection Rationale · Attribution

## Example

```text
Winner: skeptic

## Per-variant outputs
- maintainer 24/40: adds the flag but skips the empty-input case.
- skeptic 33/40: adds the flag, handles empty input, and extends the test.
- builder: unavailable (timeout).

## Winner Selection Rationale
- The skeptic is the only implementation that passes every quality gate.

## Attribution
Host-native sub-agents: maintainer, skeptic. The builder timed out.
```

## Next-step options

**Use the winner - plan it** · **Re-run with different variants** · **Done**

## Plan-brief extractor

Convert the winning output into apply-as-PR steps: file, diff, test, commit.
