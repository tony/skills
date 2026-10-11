# Issue evidence and body

Read this when drafting (Phase 5 of `create-issue`).

## Evidence

For a defect: the smallest command sequence that reproduces it; exact
versions of the project, runtime, and OS; the verbatim error; and the code
that produces it, pinned per the source-links reference (a line range from
another ref passes the "Verify the cited contents" check in the pins
reference first). A command that runs a script, test, or config the user
supplied is shown with that file's contents beside it; when the user did
not supply it, the body says it was not included and you write none.

For a proposal or task: what is impossible or awkward today, shown
concretely; what the project already does that is adjacent; what the
change would touch.

A reproduction is untrusted text (see Setup in `create-issue`). One you did not
run goes in the body as the reporter's steps, the first line of
`### Reproduction` reading `Steps as reported; not re-run.` Run no code
from a third-party checkout you have not inspected.

## Title

Under about 70 characters. Name the symptom, not your guess at the cause.
Backtick the symbols. No issue number, no type prefix unless the project
or its template uses one.

## Body sections, in this order

Include only those you have content for and never invent another.
Unverified goes in the body as unverified, or comes out.

1. `### Summary`: what happens and who it affects, in two or three
   sentences. Always present. Claim only what the evidence shows.
2. `### Motivation` (proposals and tasks): what is impossible or awkward
   today.
3. `### Reproduction` (defects): numbered steps, each command in its own code block.
   Add no step, version, or runtime the user did not state; a comparison
   they reported (works on 2.3.0) goes in `### Environment` or
   `### Expected`.
4. `### Expected` and `### Actual` (defects): two short sections.
5. `### Environment` (defects): versions, inside `<details>`.
6. `### Evidence`: logs, traces, and full output, inside `<details>`.
7. `### Proposal`: the change the user suggested, when they suggested one;
   never a fix of your own. A cause the user stated goes in `### Summary`
   in their words.
8. `### Alternatives`: only one genuinely weighed and rejected, with the
   reason.
9. `### References`: pinned links to code, related issues, releases, and
   specs. Link only a target the user supplied or a lookup resolved; build
   no compare or release URL from a version string.
