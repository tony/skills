# The verification contract

The rule behind `double-check` and the `double-check-align` skill. Host projects
can copy the fragment at the bottom into their own AGENTS.md.

## Contents

- The contract
- Banned in the output
- The adopted-state exception
- What this contract is not
- AGENTS.md fragment

## The contract

When re-verifying, the deliverable is the re-derived answer,
standalone, in the shape the original request implied, as if answering
for the first time.

- Baseline is the source, not the transcript. Re-open the files,
  issues, data, or specs and re-derive every claim. The prior answer
  is untrusted scratch for recalling which sources exist.
- Verification is performed, not asserted. Cite what you re-opened and
  what it said, or the command you ran and its output. "Verified
  earlier in this conversation" is not evidence.
- Derive the outline from the source and the original request, not from
  the prior answer's numbering, so omissions become visible.
- Confidence lives on the claim, not the revision. Write "weak
  evidence: X only follows if Y", never "X was overstated".

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
the old claim. Did they act on it (commit, file, send, build on it)? Then say once, briefly, whether it holds ("the issue filed
earlier claims X; the source says Y"), then continue standalone.
Adoption is the only thing that turns a prior turn into a baseline.

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
