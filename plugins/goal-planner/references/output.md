# Output contract

Use these exact level-2 headings in the declared order. Write prose under
[prose-rules.md](prose-rules.md). Omit empty details within a section; do not
invent additional top-level sections.

## Print and synthesize replies

1. `## Goal`: one text code block with the complete exact helper `payload`.
   Never abbreviate it, use ellipses for omitted clauses, or replace it with
   a link. When stdout-only leaves a required companion unsaved, include its
   complete contract in a second text block here and mark the compact draft
   incomplete. A save error never removes the printed goal.
2. `## Handoff`: readiness, host, measured condition and whole-payload counts
   in code points and UTF-16 units, and remaining capacity where bounded.
   Include saved goal/specification links, revision/reuse status, digest, and
   concrete save or verification failures when applicable. Counts and save
   notices are outside the copyable payload.
3. `## Coverage`: concise assumptions, provenance and recovery gaps, accepted
   evidence, and unresolved requirements. Synthesis includes every input
   requirement's disposition, grouping unchanged requirements when readable.
4. `## Next steps`: only relevant choices such as revise the draft, independently
   audit it, or transfer its bundle. Do not activate or execute the goal.

The first text block must preserve every payload character, including any
trailing newline. Keep fences and the separator before the closing fence outside
the saved bytes; that separator alone does not add a newline to the payload.
If the payload ends in a newline, add a blank line before the closing fence
so removing only the separator preserves that newline. If the payload has
backticks, choose a longer fence. Check any presentation transformation before
sending; a correct file with an abbreviated final reply still fails.

## Audit replies

1. `## Verdict`: PASS, FAIL, PARTIAL, or UNVERIFIED for the exact reviewed
   revision/digest, with reviewer independence and evidence limits.
2. `## Blocking findings`: requirement, evidence, impact, and correction for
   each mandatory failure. State when none were established.
3. `## Recommendations`: useful optional changes, separate from blockers.
4. `## Coverage`: original sources reviewed, requirement verdicts, excluded
   scope, unavailable checks, and remaining uncertainty.
5. `## Next steps`: revise, obtain missing evidence, or accept the reviewed
   draft when justified. Auditing never silently edits or activates it.

## Profile replies

1. `## Profile`: complete proposed or saved profile values, identifying explicit
   user selections separately from candidates awaiting selection.
2. `## Bindings`: selected machine bindings or unresolved local capabilities;
   keep private paths out of portable profile values.
3. `## Changes`: changed defaults, provenance, persistence status, and concrete
   validation failures. Never imply that a proposal changed configuration.
4. `## Next steps`: select unresolved candidates, revise, or transfer approved
   defaults without raw history.

For the final next-step section, use `AskUserQuestion` when available; skip
the panel when already in plan mode. Without a question tool, print the choices
as a plain list and stop. Choices cannot imply authority beyond the request.
If drafting cannot proceed at all, print one result sentence and the exact
missing decision or source. If a draft exists, print it despite save failure.
