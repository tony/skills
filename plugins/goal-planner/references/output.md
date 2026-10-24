# Output contract

Use these exact level-2 headings in order and [prose-rules.md](prose-rules.md).
Omit empty details, not prescribed sections; add no other top-level sections.

## Print and synthesize replies

1. `## Goal`: a text block containing the complete exact helper `payload`,
   never an abbreviation, ellipsis, or replacement link. If a required
   companion is unsaved, print its complete contract in a second block and
   mark the compact draft incomplete. Save errors never suppress the goal.
2. `## Handoff`: readiness, delivery host, condition/whole-payload counts in
   code points and UTF-16 units, and bounded remaining capacity. Include saved
   goal/specification links, revision/reuse, digest, and concrete save or
   verification failures. Keep measurements and notices outside the payload.
3. `## Coverage`: assumptions, provenance, recovery gaps, accepted evidence,
   and unresolved requirements. Synthesis gives every input requirement a
   disposition; group unchanged requirements where readable.
4. `## Next steps`: relevant choices such as revise, independently audit, or
   transfer the bundle. Never activate or execute it.

Preserve every payload character, including trailing newlines. Fences and the
separator before the closing fence are outside saved bytes. When the payload
ends in a newline, add a blank line before closing so removing only the
separator preserves that newline. Use a longer fence if the payload contains
backticks. Verify presentation too: a correct file with an abbreviated reply
still fails.

## Audit replies

1. `## Verdict`: PASS, FAIL, PARTIAL, or UNVERIFIED for the exact revision/digest,
   with reviewer independence and evidence limits.
2. `## Blocking findings`: requirement, evidence, impact, and correction for
   mandatory failures; state when none were established.
3. `## Recommendations`: optional changes, separate from blockers.
4. `## Coverage`: originals reviewed, requirement verdicts, exclusions,
   unavailable checks, and uncertainty.
5. `## Next steps`: revise, obtain evidence, or accept when justified.
   Auditing never silently edits or activates the goal.

## Profile replies

1. `## Profile`: complete proposed/saved values; distinguish explicit user
   selections from candidates awaiting selection.
2. `## Bindings`: selected bindings or unresolved capabilities; keep private
   paths outside portable preferences.
3. `## Changes`: defaults changed, provenance, persistence, and validation
   failures. A proposal does not change configuration.
4. `## Next steps`: select candidates, revise, or transfer approved defaults
   without raw history.

Use `AskUserQuestion` for the final choices when available; skip the panel in
plan mode. Without a question tool, print choices as a list and stop. Choices
grant no additional authority. If drafting cannot proceed, print one result
sentence and the exact missing source/decision. If a draft exists, print it
despite rendering or save failure.
