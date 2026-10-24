# Goal contract

Write the complete requested outcome before shortening it. Apply
[prose-rules.md](prose-rules.md) to the contract and its explanations.

## Identity and requirements

Identify the target repository or artifact, goal key, revision, predecessors,
and `DRAFT_NOT_STARTED` state. Keep descriptive, stable requirement keys
such as `installed-consumer`; namespace unrelated targets before combining
colliding keys. Keys are traceability data, not substitutes for readable prose.

Every binding requirement needs an observable acceptance condition, evidence
source, and disposition. Retain the full outcome, deliverables, dependencies,
ownership, and ordering. Keep a small goal in a few paragraphs; add structure
only when it prevents a mistake. Do not create empty stage files or duplicate
the contract in a second hand-maintained format.

Carry exclusions through research, implementation, documentation, tests, and
review. An excluded package cannot become a derived blocker through a test
matrix or review rubric. Distinguish exclusions from unsupported platforms,
unverified behavior, and accepted limitations.

## Authority and reconciliation

Apply the instruction hierarchy, current task-specific steering, applicable
project rules, and selected approved defaults. History supplies context.
Do not resolve conflicts between authoritative instructions by timestamp
alone. Current implementation can change remaining work; it cannot redefine
the user's intended outcome.

Separate present authorization from actions proposed after activation.
Printing does not activate work, replace a standing goal, or authorize
commits, pushes, publication, installation, or release. Preserve established
session permission without asking again for routine authorized steps. Preserve
research-only and timing holds; reaching an earliest permitted time is not
activation. A composed request may separately authorize concrete preparation.

Inspect only current source, branches, PRs, CI, artifacts, and resources
needed to assess this goal. Preserve contrary evidence and unresolved failures.
Never infer completion from an earlier agent's assertion alone.

## Synthesis

Read full original goals, referenced specifications, and adjacent corrections.
Keep requirement provenance and assign every input requirement a disposition:
retained, revised, superseded, deferred, excluded by explicit instruction, or
unresolved. State the source of a revision or exclusion. Latest explicit user
steering can relax earlier timing or compatibility requirements.

Remove completed work from the remaining-work view only with valid evidence;
retain its acceptance criteria and evidence in the contract. Missing originals
or pasted bodies remain gaps. Do not merge unrelated target identities merely
because their requirement labels match. User addenda become sourced steering
in a new revision; do not edit an old saved specification silently.

## Acceptance and continuation

Use PASS, FAIL, PARTIAL, and UNVERIFIED precisely. A numeric score cannot
override a failed mandatory condition. Excluded work is outside scope, never
a passing check. An accepted limitation needs explicit disposition and cannot
conceal failure of a binding criterion.

Tie acceptance evidence to relevant contract, source, configuration, and
review-rule revisions. Check mutable external evidence when the contract
requires it: a local digest cannot establish the current remote CI head.
When accepted inputs are unchanged, reuse results without new experiments,
reviewers, or writes. Changed inputs reopen only affected evidence.

Include recovery, live-job waits, partial results, and completion conditions
when needed. A blocked stage must identify the actual unmet condition and
useful independent work. Challenge invented guarantees that create an impasse;
do not erase genuine obligations to make the goal appear complete.

## Review packet

Bind a review to the exact goal/specification revision or digest, original
request, lineage, and evidence. Provide relevant failure conditions and scope
boundaries. Require requirement-by-requirement findings rather than confidence
alone. Preserve the reviewed revision and disagreements when revising it.

Select extra checks from [safeguards.md](safeguards.md). Compression and saved
handoffs follow [rendering.md](rendering.md); presentation follows
[output.md](output.md).
