# Fix-review results

## Hero

`N fixes applied, M skipped`

## Sections, in order

Applied Fixes · Tests Added · Skipped Findings · Final Verification · Attribution

## Example

```text
2 fixes applied, 1 skipped

## Applied Fixes
- Bound the retry loop (commit a1b2c3d).
- Count failed requeues (commit d4e5f6a).

## Tests Added
- test_retry_stops_on_4xx extends the parametrized retry cases.

## Skipped Findings
- Rename the constant: the file has your uncommitted edits.

## Final Verification
- Formatter, linter, and tests pass.

## Attribution
Findings came from the weave review in this conversation.
```

## Next-step options

**Review the branch again** (suggest the `weave-review` skill) · **Done**
