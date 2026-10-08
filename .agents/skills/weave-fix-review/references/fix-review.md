# Fix-review results

Final Verification reports only gates that already ran, from the last gate run after the final commit; name a gate that could not run once, with the reason.

## Hero

`N fixes applied, M skipped`

## Sections, in order

Applied Fixes · Tests Added · Skipped Findings · Final Verification · Attribution

Keep every section. Write "None." when no tests were added or no findings were skipped.
Each applied fix states that it was committed, not merely a proposed commit
subject. If mentioning pre-existing user edits, say they remain outside the
commit with their original staged/unstaged state.

## Example

```text
2 fixes applied, 1 skipped

## Applied Fixes
- Bound the retry loop; committed as "fix(retry) Cap attempts".
- Count failed requeues; committed as "fix(queue) Count failures".

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
