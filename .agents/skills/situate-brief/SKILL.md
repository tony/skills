---
name: situate-brief
description: >-
  Use when confusion is only “huh,” “wait, what,” “sorry, you lost me,” or
  “slow down; explain simply and keep it short.”
allowed-tools: ["Bash", "Read", "Grep", "Glob"]
metadata:
  source: "plugins/situate/skills/brief/SKILL.md"
---

# Brief

Someone just said "huh". Give them five lines and get out of the way.

Read `references/brief.md` before answering. It carries the
five-line budget, the ranking that decides what earns a line, the option
format, and the evidence tiers. the `situate-what` skill is the explicit entry
point to the same contract. Stay read-only, per the contract in
`references/situation-sweep.md`.

## Recognizing the trigger

The signal is a question with no subject: a bare interrogative, a
request to back up, or an admission of being lost. "What does the parser
do" names its object and is an ordinary question; answer it normally.

When unsure, answer briefly rather than asking which they meant.

A request to be caught up ("bring me up to speed on this branch", "what
is this pull request waiting on") names what it wants and wants it in
full. That is `situational-awareness`, and `/situate` is its explicit
form.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
