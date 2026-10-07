---
name: situational-awareness
description: "Use when the user is back on a branch or PR and says \"bring me up to speed\" or \"I'm back\": where it left off, repo state, what reviews ask."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
---

# Situational awareness

Establish what is going on in a repository before acting in it.

Read `../../references/situation-sweep.md` first, and
`../../references/prior-conversations.md` before searching local AI
transcripts. Search them when the repository does not explain itself
and always when the request is to resume after a gap: that request
counts as asking.

A bare "huh" or "what?" is not this skill; `brief` answers it. This one
runs when someone can already say what they want caught up on.

## Procedure

1. Gather every layer of the sweep before reporting anything: a ticket's
   acceptance criteria change what the diff means, and an unresolved
   review thread explains a commit that looks like a detour.
2. When the user is resuming after a gap, run the capped
   prior-conversations search before reporting, deriving terms from what
   the repository layers found.
3. Report in the shape in `../../references/report-shape.md`, written
   per `../../references/prose-rules.md`. Lead with what is
   unresolved: the open questions, the failing check, the half-finished
   edit, and any decision an earlier conversation left open (cite it as
   an earlier conversation with its date, or "undated" when the record
   has none; a decision in this session's own context is "earlier in this
   session"). Someone asking to be caught
   up does not want a narration of what already works.
4. Say which layers were unavailable and why.
