# Output contract

Use these level-2 headings in order and [prose-rules.md](./prose-rules.md).
Include optional sections only when they carry information the user needs.
End completed handoffs without a choice menu or a closing offer.

## Print and synthesize replies

1. `## Goal`: a text block containing the complete exact helper `payload`,
   never an abbreviation, ellipsis, or replacement link.
2. `## Specification`, when a required specification is unsaved or its pair
   fails saving or verification: the complete specification in a fenced `text`
   block.
   Mark the handoff unsaved/incomplete and distinguish any partial files.
   Save errors never suppress the goal or required specification.
3. `## Handoff`: one short status line with host, limit (or no selected cap),
   `Counts: N code points; N UTF-16 units.`, and saved/reused/not-saved/incomplete.
   Keep it outside the payload. Saved identities follow on separate lines:
   goal/specification paths and revision/reuse; do not repeat a companion digest
   already in the goal. Add details only for material gaps/errors or requested
   explanations. Omit routine assurances, helper narration, and Unicode lessons.
   State failures without claiming readiness.
4. `## Coverage`, when needed: material assumptions, provenance/recovery gaps,
   or unresolved requirements. Synthesis always gives inherited requirements
   keyed dispositions, grouping unchanged requirements where readable. Ordinary
   standalone drafts need no coverage inventory or empty section.

Preserve every payload character, including trailing newlines. Fences and the
separator before the closing fence are outside saved bytes. When the payload
ends in a newline, add a blank line before closing so removing only the
separator preserves that newline. Use a longer fence if the payload contains
backticks. Verify presentation too: a correct file with an abbreviated reply
still fails.

## Audit replies

1. `## Verdict`: PASS, FAIL, PARTIAL, or UNVERIFIED for the exact reviewed goal,
   with its full SHA-256 digest, saved revision when present, reviewer
   independence, and evidence limits.
2. `## Blocking findings`, when present: requirement, evidence, impact, and
   correction for mandatory failures.
3. `## Recommendations`, when useful: optional changes, separate from blockers.
4. `## Coverage`: originals reviewed, requirement verdicts, exclusions,
   unavailable checks, and uncertainty.

Keep draft omissions distinct from execution evidence: a required consumer
check absent from the draft is a draft FAIL; an unrun consumer check remains
UNVERIFIED. Auditing never silently edits or activates the goal.

## Profile replies

1. `## Profile`: complete proposed/saved values; distinguish explicit user
   selections from candidates awaiting selection.
2. `## Bindings`, when selected or unresolved: machine values/capabilities;
   keep private paths outside portable preferences.
3. `## Changes`: compact persistence status, changed defaults, provenance,
   and validation failures. A proposal does not change configuration.

Ask only for missing decisions needed to finish the request; use an available
question tool or a direct question. If drafting cannot proceed, print one
result sentence and the exact missing source/decision. If a draft exists,
print it despite rendering or save failure. A handoff grants no execution
authority and never activates a native goal.
