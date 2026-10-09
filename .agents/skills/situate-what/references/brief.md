# The brief

Shared by this skill and the `brief` skill.

Five lines, maximum. The reader is disoriented; every line they read
before that ends is a cost. The full sweep is exhaustive because its
reader is about to touch the code; the brief is capped at five lines because
its reader has just said "huh".

Script paths here (`../scripts/...`) resolve from this file's directory, not the repository: use the absolute directory this file was read from, written literally in each command.

## Contents

- The budget
- What earns a line
- Drop, do not pad
- Options
- Evidence budget
- Confidence
- Banned
- When nothing is going on

## The budget

Five lines of body. One sentence each, no sub-clauses stacked to smuggle
a sixth fact into the fifth line. No headings, no bullets, no bold, no
preamble, no closing summary.

Option lines are separate and do not count. Everything else does.

Three lines that land beat five that pad.

## What earns a line

Fill from the top of this ranking and stop when the situation runs out
or the budget does:

1. **The blocker.** What is stopping progress right now — a failing
   check, an unanswered question, a conflict, a decision waiting on the
   user. If something is blocked, it is line one.
2. **Where the work sits.** Branch against trunk, pull request state,
   uncommitted work. Compress to one line: `feat-x, 4 commits, PR #12
   open, 2 files uncommitted`.
3. **What just happened.** What this session did or was midway through.
   On a resumed session with no history, what the last commits did
   instead.
4. **What it is for.** The goal, when it is not obvious from the branch
   name or when the work has wandered from it.
5. **What is outstanding.** What remains before this is done.

A fact that fits two slots is stated once, in the higher one.

## Drop, do not pad

Unlike the full sweep, report absence only when it is load-bearing:
"No pull request open" on a finished branch is the finding; on a branch
one commit old it is noise. Never spend a line saying a layer was
checked and was boring.

## Options

After the body, optionally offer choices — each exactly one line,
numbered, so the reader can answer with a digit instead of a sentence.

Offer them only when there is a real fork; an obvious next step ends at
the body.

Offer no option the session cannot back: no fix the explanation never
gave, no pointer into code when there is no repository. Two to four
options. Each names an action, not a topic: `2. Resolve the
three review threads on PR #12`, never `2. Review feedback`.

Do not use `ask-user-choice`; a modal panel is heavier than the five
lines it follows.

## Evidence budget

Work outward in tiers and stop as soon as the five lines are earned.

**Free — always.** What this session already knows. If a sweep already
ran, or the session has been working in this repo, that is the evidence;
re-reading what is already in context is the common way this gets slow.

**Cheap — run when the session's own memory is thin.** The position
script (`references/position.py`: branch, trunk, ahead/behind,
uncommitted work) and the branch's commit subjects. These are local and
fast. A narrow file question takes only that file's status and diff;
unrelated branch, trunk, and remote lookups earn no line, even if unavailable.

**Paid — only on an existing reference.** `gh pr view` when the branch
actually has a pull request, `gh issue view` when a ticket ID appears in
the branch name, a commit, or the pull request body. Skip both when the
session already knows their state and the question does not require a
fresh observation. Otherwise refresh the referenced item or describe its
state as last observed; cached CI or review state is not a current check.

**Never.** `git fetch`, full diff reads, transcript search, convention
files.

When a paid layer is unreachable — no `gh`, no network — say so inside
an existing line rather than spending a line on the tooling.

## Confidence

State only what the evidence supports, and mark at most one inference
per brief with a single hedging word, never a guess at a person's
motive or intent. Two hedges means the brief is
guessing and should say what it does not know instead.

## Banned

- Preamble. Not "Here's what's going on" — just what is going on.
- Restating the question back before answering it.
- File and path inventories. The reader can run `git status`.
- References to earlier turns: "as I mentioned", "as noted above".
- Apology or self-assessment about the confusion that prompted the ask.
- Any line that would be true in every repository on any day.
- A guess at why uncommitted work was left, or an option phrased as
  "what was probably intended".
- Bullets, bold, and headings.
- Diagnosing drift. If the work has wandered from what it was for, say
  so in one line and offer the `situate-refocus` skill as an option.

## When nothing is going on

A clean tree on trunk with nothing in flight is a one-line answer, and
the option lines carry more value than the body: say it is clean and
offer the plausible starts.
