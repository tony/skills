---
name: respond-check
description: >-
  Use when screening pull-request review comments and bot findings; decide
  fix, defer, or decline for each, and draft (not post) replies.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[findings text] [<pr-number|url>] [--base=<ref>] [--include-resolved]"
  source: "plugins/respond/skills/check/SKILL.md"
---

# this skill

Screen review feedback and decide what deserves a fix. Every claim,
from a colleague, a bot, or a review command run earlier in this
session, is tested against six gates and leaves with a verdict, its
evidence, and a reply the reviewer can argue with.

**This skill changes nothing.** No edits, no commits, no comments
posted, no threads resolved. Its entire output is a ledger and a
recommendation; acting on it is the `respond-action` skill's job.

## Core thesis

A claim is not a work order. Every verdict carries its evidence, so a
reviewer who disagrees can attack the evidence instead of the judgment.

`references/screening-rubric.md` is the authority on the gates,
verdicts, and ledger; this skill collects the inputs and reports the
outputs.

## `$ARGUMENTS` contract

A leading pull request number or URL names the PR to collect from
(default: the current branch's PR when one exists); other non-flag text
is the findings list. With no arguments and no PR,
look for review output already in this session; if there is none, ask
for the feedback rather than inventing a review.

| Flag | Default | Effect |
|---|---|---|
| `--base=<ref>` | merge-base with `origin/<trunk>` | Override the provenance baseline (a stacked branch's parent, for instance). |
| `--include-resolved` | off | Screen resolved and outdated threads too, instead of treating them as already settled. |

## Phase 0: What this project has already decided

The alignment gate needs citations, so gather them before reading a
single finding: `AGENTS.md` / `CLAUDE.md` and any nested equivalents
covering the touched directories, `.github/CONTRIBUTING.md`, and the
branch's own stated purpose — its pull request body, its commit
messages, its ticket.

Resolve the provenance base here too (see the rubric's Provenance
gate), and note the branch's push state with `git status -sb`. This
skill does not fetch, so `origin/<trunk>` is read as last fetched; say
in the report that provenance may be stale when the remote has moved.

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

Disciplines while screening:

- **Read the code, do not trust the claim.** Automated reviewers assert
  with total confidence regardless of whether they are right.
- **Cost the smallest fix that works**, per the rubric's cost gate.
- **One verdict per finding.** "Fix if X" is not a verdict; when the
  code cannot be read, the verdict is `ask`.
- **Decline on evidence only**: a cited decision, a code path read, a
  trigger named. "That isn't long" is a preference, not evidence.
- **Add no support the code and the reviewer's text do not give.** No
  standards, library functions, or rationale you have not verified, per
  `references/prose-rules.md`.

Use `ask-user-choice` for `ask` verdicts only: findings where the
truth depends on intent only the author has, where the alignment
citation is genuinely contested, or where the code is not available.
Everything else is decided here. In a non-interactive run, leave them
as `ask` in the ledger.

## Phase 3: Report — the output contract

Write the report and replies per `references/prose-rules.md`. Use
exactly the headings below, in this order, and no others. Never name
local absolute paths or temp files.

1. Hero block (1–3 lines): `N to fix, M deferred, K declined` plus the
   branch name and the feedback sources screened.
2. `## Ledger` — one entry per finding: id, source (author, and whether
   it is a bot), the claim quoted, location, the gate results with
   their evidence, and the verdict with its reason. Merged duplicates
   list all their sources on one entry.
3. `## To fix` — the accepted findings in the order they should land,
   each with the minimal fix and whether it wants a forward commit or a
   `fixup!`. Name a `fixup!` target only when the branch's log shows
   the causal commit; otherwise it is a forward commit.
4. `## Deferred & declined` — with the follow-up recommendation or the
   drafted reply. A declined `improbable` reply states the trigger the
   scenario needs, so a reviewer who knows a caller that produces it
   can say so.
5. `## Ledger key` — branch, `HEAD` SHA, and the feedback digest, as
   the rubric's ledger section defines them. the `respond-action` skill checks
   this key to know the screening still describes the current tree.
6. End with an `ask-user-choice` panel: run the `respond-action` skill on the
   accepted findings, run it with `--reply` so the drafted replies get
   posted too, re-screen with the deferred findings opted in, or stop.
   In a non-interactive run (CI, subagent), list the panel's options as
   plain numbered lines after `## Ledger key`, with no heading, and stop.
   Invoked by the `respond-goal` skill, skip the panel.

A stopped run (no findings to screen, no readable feedback) reports one
result sentence, then what the user needs to provide.

Nothing in this phase edits, commits, or posts. If the run reaches a
point where a fix seems obvious enough to just do, that is the failure
mode this skill exists to prevent — write it in `## To fix` and hand
off.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
