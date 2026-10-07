---
name: double-check-align
description: >-
  Use when prior verification was framed as a revision log and the user
  wants a clean, standalone restatement.
disable-model-invocation: true
allowed-tools: ["Read", "Grep", "Glob"]
metadata:
  argument-hint: "[topic or question to re-anchor on]"
  source: "plugins/double-check/skills/align/SKILL.md"
---

# this skill

Recovery for a broken double-check. The chat holds a revision log:
verdicts about prior claims, deltas against text the user never read.
Replace it with the analysis itself.

Phrases to avoid: `references/verification-contract.md`.

## `$ARGUMENTS`

- Empty — re-anchor on the subject of the most recent analysis
  thread, at its original scope.
- A topic or question — re-anchor on that instead. Narrowing is a
  feature: it discards the earlier answer's scaffolding, which is
  what lets omitted items finally surface.

## Steps

1. Reconstruct the original question and every constraint the user has
   added since, including corrections they made that you agreed with.
   User turns are binding context; your own answer turns are not.
2. Re-open the source artifacts and write the full analysis,
   standalone, in the shape the original request implied, with no
   reused numbering, category names, or verdict framing. State every
   claim positively and in full, per `references/prose-rules.md`.
   If a claim is weak, say why it is weak; never say it was previously
   stated differently.
3. Check for adopted state: did the user commit, file, or send a prior
   claim? Then add one sentence saying that claim is wrong and what the
   source says, and continue standalone. Otherwise the prior turn does
   not appear in your output.

Halt only after trying: when `$ARGUMENTS` is empty and no analysis
thread exists, or a named source will not open, restate nothing. Reply
with one result sentence, then what the user must supply (a topic, or
the file's path).

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
poller.py sets POLL_INTERVAL_SECONDS = 30 and MAX_POLLS = 4.

- The loop checks the job status at most 4 times.
- It sleeps 30 seconds between checks, so a job that never finishes
  costs 90 seconds of waiting before TimeoutError is raised.
```

## What this does not do

- Reference, summarize, or grade the earlier response, except the one
  adopted-state sentence in step 3.
- Edit files or commit — output is conversation only.
- Answer a different question than the one recovered or given —
  losing focus is the failure this command repairs.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
