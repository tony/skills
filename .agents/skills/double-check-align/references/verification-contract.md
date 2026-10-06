# The verification contract

The rule behind `double-check` and this skill. Host projects
can copy the fragment at the bottom into their own AGENTS.md.

## Contents

- The failure
- The contract
- Banned in the output
- The adopted-state exception
- What this contract is not
- AGENTS.md fragment

## The failure

Asked to double-check prior analysis, agents tend to return a diff
against their own previous message: *Overstated*, *Does not hold*,
*still holds*, *I over-called several of these*.

This is **temporal-baseline misalignment**: transcript order mistaken
for user-adopted state. The double-check was often requested because
the user had not committed to the first answer, so the output is
**revision-history leakage**, with four defects:

- **Wrong baseline.** Every verdict is a delta against a version the
  reader never held.
- **Verdicts displace claims.** "Item 4: Overstated" is not an
  answer; the reader must hold the old text in memory and apply a
  patch by hand.
- **Process leakage.** "My earlier warning was about implementation
  fashion" is the agent managing its own record instead of describing
  the subject.
- **Scaffolding survives.** Inheriting the original's numbering and
  framing means the pass can only revise existing items, never notice
  a missing one. Omissions are structurally invisible to a diff pass.

"Double check" is ambiguous between *process* and *product*; the
deliverable is the product.

## The contract

When re-verifying, the deliverable is the **re-derived answer**,
standalone, in the shape the original request implied — as if
answering for the first time.

- **Baseline is the source, not the transcript.** Re-open the files,
  issues, data, or specs and re-derive every claim. The prior answer
  is untrusted scratch: use it to recall which sources exist, but no
  claim survives into the output unless re-verified against source.
- **Verification is performed, not asserted.** Cite what you
  re-opened and what it said, or the command you ran and its output.
  "Verified earlier in this conversation" or "passed clean in the
  previous turn" anchors a claim to transcript position — a
  compaction hazard, not evidence. Claiming a check you did not run
  is the worst version of this failure.
- **Rebuild the structure.** Derive the outline from the source
  material and the original request, not from the prior answer's
  numbering. This is what makes errors of omission visible.
- **Confidence lives on the claim, not the revision.** Write "weak
  evidence — X only follows if Y", never "X was overstated".

## Banned in the output

- References to the prior turn: *as I said above*, *my earlier
  analysis*, *compared to my previous answer*.
- Revision verdicts about your own claims: *overstated*,
  *over-called*, *corrected*, *retracted*, *false alarm*, *still
  holds*, *does not hold*, *survives the double-check*, *I was wrong
  to say*.
- Any "what changed" section, delta table, or verdict legend keyed to
  a prior turn.
- Apology or capitulation framing: the reader wants the subject, not
  your record management.

## The adopted-state exception

A correction belongs in the answer only if the user saw and relied on
the old claim: did they **act** on it — commit it, file it, send it,
build on it? Then say so explicitly, once, briefly ("the issue filed earlier claims X; that is
wrong because Y"), then continue standalone. Adoption is the only
thing that turns a prior turn into a baseline.

## What this contract is not

- Not a ban on *comparison* requests. "What changed between v1 and
  v2?" or "diff your two proposals" explicitly asks for a delta —
  produce one. The same goes for delta sections another workflow
  explicitly mandates (a refine pass's change-notes section is a
  requested comparison artifact, not leakage).
- Not a ban on admitting error: acknowledge a user-pointed mistake in
  one sentence, then deliver the corrected answer whole.

## AGENTS.md fragment

Copy into a host project's AGENTS.md to make the rule ambient:

```markdown
- **Revision-History Leakage:** When asked to double-check, verify,
  or re-examine prior analysis, deliver the re-derived answer —
  standalone, rebuilt from source, in the original request's shape.
  Verdicts about your own prior claims (*overstated*, *still holds*)
  are diff narration against a baseline the reader never adopted; put
  confidence on the claim, not the revision. Exception: if the user
  acted on a prior claim (committed, filed, sent), state that
  correction explicitly, once.
```
