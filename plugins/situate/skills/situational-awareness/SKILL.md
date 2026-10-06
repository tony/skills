---
name: situational-awareness
description: "Use when you came back to a branch/PR: the work you were in the middle of, where it left off, repo state, and what reviewers ask or the PR waits on."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
---

# Situational awareness

Establish what is going on in a repository before acting in it: what
the branch does, how far along it is, what its pull request and tickets
ask for, and what the project's own rules require of the work.

Read `../../references/situation-sweep.md` first. It defines the six
evidence layers, how each degrades, and the read-only contract. Read
`../../references/prior-conversations.md` before searching local AI
transcripts. Search them when the repository does not explain itself
(an approach with no recorded rationale, a decision that left no
artifact) and always when the request is to resume after a gap: that
request counts as asking.

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
   the earlier conversation, with its date). Someone asking to be caught
   up does not want a narration of what already works.
4. Say which layers were unavailable and why.
