---
name: double-check
description: >-
  Use when asked to double-check, verify, “are you sure/certain”, or “I
  don't trust that”; recheck from source and repeat the earlier analysis in
  full.
metadata:
  source: "plugins/double-check/skills/double-check/SKILL.md"
---

# Double-check

Re-verify by re-deriving. The deliverable is the verified answer,
not a record of how it differs from your last one.

Phrases to avoid, and why a verdict list against your prior answer
fails: `references/verification-contract.md`.

## Steps

1. Recover the original question, its constraints, and any narrowing
   the user added since. Treat your prior answers as scratch for
   recalling which sources exist.
2. Re-open the artifacts and re-derive each claim, outlining from the
   source and the request. Name what you re-opened and what it said, or
   the command you ran and its output.
3. Check for adopted state: did the user commit, file, send, or build
   on a prior claim? Then state that correction once, in one sentence
   (the user's figure is wrong, the source says X), and continue
   standalone. Otherwise the prior turn does not exist in your output: never write
"my earlier figure was wrong" or similar.

If the chat holds no prior answer, treat the request as a first ask and
verify the claim the user names. If the claim has no checkable artifact
(a web fact, a memory), say which source you can reach and which you
cannot; never answer "verified" from recall.

## Output shape

Same shape the original request implied, as if answering for the first
time. Name each file you re-opened or command you ran, relative to the
project. No "what changed" section, no verdict legend, no *as noted
above*, unless the user explicitly asks for a comparison ("what changed
between v1 and v2?"); then produce the delta they asked for. Write it
per `references/prose-rules.md`.

When a narrow request ("are you sure about X?") scopes the answer to X,
still append anything material you discovered while re-deriving, as a
standalone fact about the subject ("the ADR also permits Y"), never as a
correction of your prior answer.

When the artifact cannot be opened, nothing is verified. Reply with one
result sentence, then what the user must supply:

```text
I could not open client.py, so nothing here is verified. Paste the file
or give its path in the project and I will re-derive the answer.
```

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
client.py sets MAX_RETRIES = 3 and RETRY_BACKOFF_SECONDS = 2.

- send_with_retry loops while attempts < MAX_RETRIES, so it makes 3
  send attempts in total (client.py).
- Backoff is RETRY_BACKOFF_SECONDS = 2, slept after every failed
  attempt, including the last, so a fully failing call sleeps 6
  seconds before returning None.
```


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
