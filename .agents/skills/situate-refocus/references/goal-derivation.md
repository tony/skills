# Deriving the goal, and measuring drift against it

Used by this skill.

## Contents

- The goal is derived, never stored
- Precedence
- When sources disagree
- Drift has two sides
- Classify, do not just flag
- Why it happened
- Realigning

## The goal is derived, never stored

Every invocation re-reads the goal from the project's own artifacts.
Nothing is written to disk and nothing carries over between sessions.

A stored goal goes stale the moment the ticket is edited or the scope is
renegotiated in a comment, and the user resuming after a gap has no
memory to check it against. A goal the user only said out loud in an
ended session is not recoverable: say the goal came from the branch name
and is weak, rather than presenting a guess as the record.

## Precedence

Take the first source that yields a goal, and say which one it was.

1. **What the user stated in this session.** Binding, and it beats every
   artifact, even where the ticket says otherwise.
2. **The linked ticket's acceptance criteria.** The body, not the title.
   Resolve
   ticket IDs from commits, the branch name, and the pull request body
   only.
3. **The pull request body.** What the branch claims to deliver, in the
   author's own words. Fall back to its title only if the body is empty
   or a template.
4. **The branch name and its first commit.** Weak but usually
   directional.
5. **Nothing.** Say so and ask. A goal inferred from the diff cannot
   detect drift in it, since every commit trivially matches.

## When sources disagree

The ticket is what was asked for; the pull request is what is being
delivered. A gap between them is a finding: either the scope moved
without the ticket, or the branch solves a different problem than the
one filed. Report both readings and let the user say which is current.

## Drift has two sides

**Work the goal never asked for.** Commits and uncommitted changes that
do not serve the stated outcome.

**Work the goal asked for that has not happened.** Acceptance criteria
with nothing on the branch addressing them; invisible until something
checks the criteria one by one.

## Classify, do not just flag

Sort every commit and every uncommitted change into three buckets.

**On goal.** Directly serves a stated outcome.

**Load-bearing detour.** Not in the goal, but the goal could not land
without it — a broken fixture that blocked the test, a dependency bump
the new code required, a rename the compiler forced. This is correct
work and must not be reported as drift. Say what it unblocked.

**Off goal.** Neither serves the outcome nor unblocked it. This is the
drift. Name where it started — the first commit that departed — because
that commit usually explains the whole excursion.

## Why it happened

When there is off-goal work, name the pattern:

- Repairing something noticed in passing while touching the file
- A failing check dragging in an unrelated fix to get green
- Review feedback that expanded scope without the ticket following
- Gold-plating a piece that already met the criteria
- A rabbit hole opened by an assumption that turned out wrong

## Realigning

Produce the assessment and the corrective options; execute nothing.
Branch surgery, reverts, and scope edits are the user's call.

Four correctives:

- **Finish the gap.** Name the unaddressed criteria in priority order.
- **Defer the off-goal work.** Split it to a follow-up branch or file it
  as its own issue, so it survives without holding this one open.
- **Drop it.** Correct when the excursion produced nothing worth keeping.
- **Widen the goal.** Sometimes the drift was the right instinct and the
  ticket was scoped too narrowly. Update the ticket or the pull request
  body to match what is being built rather than revert good work.

Never assume the goal wins: the user may have learned something since.
