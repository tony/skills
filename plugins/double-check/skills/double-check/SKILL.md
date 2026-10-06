---
name: double-check
description: "Use when asked “are you sure/certain” or “I don't trust that”; recheck code/files from source and repeat prior analysis in full, not just changes."
user-invocable: true
---

# Double-check

Re-verify by re-deriving. The deliverable is the verified answer,
not a record of how it differs from your last one.

Read `../../references/verification-contract.md` before responding. It
defines why a verdict list against your prior answer fails and which
phrases to avoid.

## Steps

1. **Recover the request, not the answer.** From the conversation,
   take the original question, its constraints, and any narrowing the
   user added since. Prior answers of yours are untrusted scratch —
   good for recalling which sources exist, never citable as evidence.
2. **Re-derive from source.** Re-open the artifacts — files, issues,
   specs, data — and rebuild each claim from what they actually say.
   Verification is performed, not asserted: cite what you re-opened
   and what it said, or the command you ran and its output. "Verified
   earlier in this conversation" anchors a claim to transcript
   position and does not count.
3. **Rebuild the structure.** Outline from the source material and
   the request, not from your prior answer's item numbers. A claim
   that no longer earns a place does not appear; a missing area
   appears.
4. **State confidence on claims.** "Weak evidence: X only follows
   if Y", never "X was overstated".
5. **Check for adopted state.** If the user acted on a prior claim
   (committed, filed, sent, built on it), name that correction
   explicitly, once, briefly. Otherwise the prior turn does not
   exist in your output.

## Output shape

Same shape the original request implied, as if answering for the
first time. No "what changed" section, no verdict legend, no
*as noted above*. Write it per `../../references/prose-rules.md`.

When a narrow request ("are you sure about X?") scopes the answer to
X, still append anything material you discovered while re-deriving, as a
standalone fact about the subject ("the ADR also permits Y"), never as
a correction of your prior answer.
