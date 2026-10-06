---
name: respond-check
description: >-
  Use when screening or replying to pull-request review comments and bot
  findings; decide if each comment is real, worth fixing, deferred, or
  declined.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "[findings text] [--pr=<num>] [--base=<ref>] [--include-resolved]"
  source: "plugins/respond/skills/check/SKILL.md"
---

# this skill

Screen review feedback and decide what deserves a fix. Every claim —
from a colleague, from a bot, from a review command run earlier in this
session — is tested against six gates and leaves with a verdict, its
evidence, and a reply the reviewer can argue with.

**This skill changes nothing.** No edits, no commits, no comments
posted, no threads resolved. Its entire output is a ledger and a
recommendation; acting on it is the `respond-action` skill's job.

That is also why this skill can be routed to on the model's initiative
while the `respond-action` skill and the `respond-goal` skill cannot: reaching for
screening when someone pastes a review costs a report and nothing else.

## Core thesis

A review is a set of claims, and a claim is not a work order. Screening
separates the real ones from the rest before any code moves, and does
it on the record: every verdict carries its evidence, so a reviewer who
disagrees can attack the evidence instead of the judgment.

`references/screening-rubric.md` is the authority on the gates,
verdicts, and ledger; this skill collects the inputs and reports the
outputs.

## `$ARGUMENTS` contract

Non-flag text is the findings list. With no arguments and no `--pr`,
look for review output already in this session; if there is none, ask
for the feedback rather than inventing a review.

| Flag | Default | Effect |
|---|---|---|
| `--pr=<num>` | current branch's PR when one exists | Collect from the PR's reviews, inline comments, and threads. |
| `--base=<ref>` | merge-base with `origin/<trunk>` | Override the provenance baseline (a stacked branch's parent, for instance). |
| `--include-resolved` | off | Screen resolved and outdated threads too, instead of treating them as already settled. |

## Phase 0: What this project has already decided

The alignment gate needs citations, so gather them before reading a
single finding: `AGENTS.md` / `CLAUDE.md` and any nested equivalents
covering the touched directories, `.github/CONTRIBUTING.md`, and the
branch's own stated purpose — its pull request body, its commit
messages, its ticket.

Resolve the provenance base here too (see the rubric's Provenance
gate), and note the branch's push state with `git status -sb`.

A project with nothing written down has made no decisions to cite,
which means the alignment gate will rarely fire. That is the correct
outcome, not a reason to substitute a preference for a citation.

## Phase 1: Collect

Gather from every channel `references/feedback-sources.md`
describes that applies to this run: pasted text, this session's earlier
review output, the pull request's three comment surfaces, and failing
CI.

Normalize, split, drop, and merge per that file, including its rule
for re-posts of findings declined earlier in this session.

## Phase 2: Screen

Run the six gates on every finding, in the rubric's order, stopping at
the first gate that settles it. Record each gate's evidence as you go —
the diff that settled provenance, the citation that settled alignment,
the trigger that settled odds. A verdict with no evidence behind it is
not a verdict, and the report must not contain one.

Two disciplines while screening:

- **Read the code, do not trust the claim.** Automated reviewers assert
  with total confidence regardless of whether they are right.
- **Cost the smallest fix that works**, per the rubric's cost gate.

Use `ask-user-choice` for `ask` verdicts only — findings where the
truth depends on intent only the author has, or where the alignment
citation is genuinely contested. Everything else is decided here.

## Phase 3: Report — the output contract

1. Hero block (1–3 lines): `N to fix, M deferred, K declined` plus the
   branch name and the feedback sources screened.
2. `## Ledger` — one entry per finding: id, source (author, and whether
   it is a bot), the claim quoted, location, the gate results with
   their evidence, and the verdict with its reason. Merged duplicates
   list all their sources on one entry.
3. `## To fix` — the accepted findings in the order they should land,
   each with the minimal fix and whether it wants a forward commit or a
   `fixup!`.
4. `## Deferred & declined` — with the follow-up recommendation or the
   drafted reply. A declined `improbable` reply states the trigger the
   scenario needs, so a reviewer who knows a caller that produces it
   can say so.
5. `## Ledger key` — branch, `HEAD` SHA, and the feedback digest, as
   the rubric's ledger section defines them. the `respond-action` skill checks
   this key to know the screening still describes the current tree.
   Write replies per `references/prose-rules.md`.
6. End with an `ask-user-choice` panel: run the `respond-action` skill on the
   accepted findings, run it with `--reply` so the drafted replies get
   posted too, re-screen with the deferred findings opted in, or stop.
   In a non-interactive run (CI, subagent) record the panel's options
   in the report and stop.

Nothing in this phase edits, commits, or posts. If the run reaches a
point where a fix seems obvious enough to just do, that is the failure
mode this skill exists to prevent — write it in `## To fix` and hand
off.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
