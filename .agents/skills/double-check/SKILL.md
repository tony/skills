---
name: double-check
description: >-
  Use when asked to double-check, “are you sure”, “I don't trust that”,
  verify your earlier answer, or run an analysis again; re-derive from
  source.
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
   on a prior claim? Then state once, in one sentence, whether the
   adopted claim holds and what the source says ("the ticket's cap of 5
   is wrong, client.py sets 3"; "the ticket's cap of 3 matches
   client.py"), and continue standalone. When that sentence already
   states the source value, it serves as the lead line. Otherwise the
   prior turn does not exist in your output: never write "my earlier
   figure was wrong" or similar.

If the chat holds no prior answer, treat the request as a first ask and
verify the claim the user names. If the claim has no checkable artifact
(a web fact, a memory), label the answer recall unless you opened a
source, and name the source you did open; never answer "verified" from
recall. When the source is a command with long or nondeterministic
output, run it again and quote only the lines the claim depends on.

## Output shape

Same shape the original request implied, as if answering for the first
time. Name each file you re-opened or command you ran, relative to the
project, by file name and not line number. No "what changed" section,
no verdict legend, no *as noted above*, unless the user explicitly asks
for a comparison ("what changed between v1 and v2?"); then produce the
delta they asked for. State each quantity itself ("the same 2 seconds
each time"), never as a contrast with another claim ("flat, not
exponential"). Write it per `references/prose-rules.md`.

When a narrow request ("are you sure about X?") scopes the answer to X,
still append facts the question's subject depends on that you found
while re-deriving, as a standalone fact about the subject ("the ADR
also permits Y"), never as a correction of your prior answer. Leave out
facts about other subjects.

When the artifact cannot be opened, nothing is verified. Reply with one
result sentence, then what the user must supply:

```text
I could not open poller.py, so nothing here is verified. Paste the file
or give its path in the project and I will re-derive the answer.
```

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
poller.py sets POLL_INTERVAL_SECONDS = 30 and MAX_POLLS = 4.

- wait_for_job loops while polls < MAX_POLLS, so it checks the job
  status 4 times in total (poller.py).
- It sleeps POLL_INTERVAL_SECONDS between checks but not after the
  last, so a job that never finishes costs 90 seconds of waiting
  before the function raises TimeoutError.
```


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
