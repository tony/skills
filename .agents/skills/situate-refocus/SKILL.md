---
name: situate-refocus
description: >-
  Use when a branch may have drifted from its ticket or pull-request goal
  and needs its work and gaps reclassified.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[the goal, when the repo does not record one]"
  source: "plugins/situate/skills/refocus/SKILL.md"
---

# Refocus

Work wanders. This finds out how far, in which direction, and whether
the wandering was wrong.

Read `references/goal-derivation.md` first — it
defines the precedence for deriving the goal, why nothing is stored
between runs, the three-way classification, and the four correctives.
Read `references/situation-sweep.md` for how to
resolve trunk, the base commit, tickets, and the pull request, and for
the read-only contract.

User arguments: $ARGUMENTS

## Procedure

### 1. Derive the goal

`$ARGUMENTS`, when given, is the goal and outranks every artifact.
Otherwise take the first source in the goal-derivation precedence.

Say which source the goal came from and how confident it is: acceptance
criteria and a branch name are not the same evidence. If no source
yields one, stop and ask; never infer the goal from the diff.

### 2. Read what was actually done

Resolve the base by the sweep reference's rules rather than assuming
trunk: a stacked branch takes its parent, so the range holds only this
branch's work. Report the layer unavailable, and which lookup failed,
when neither resolves.

Then read the commits since that base, the diff behind them, and the
uncommitted changes. Uncommitted work counts: drift often lives there
first.

### 3. Classify

Sort each commit and each uncommitted change into the three buckets in
the goal-derivation reference. For off-goal work, find the first commit
where it started.

### 4. Find the gap

Walk the goal's criteria one at a time and check each against the
branch. Criteria with no work behind them are drift too.

### 5. Propose the correction

Recommend one of the four correctives in the goal-derivation reference
and say why. Do not assume the goal wins: when the excursion was the
better instinct, update the ticket or pull request body to match.

## Output

Write it per `references/prose-rules.md`. Open with a one-line hero — `✓ On goal: <goal> · <n> commits`, or
`⚠ Drift: <what wandered>`, or `⚠ No goal recoverable` — then exactly
these sections:

1. `## Goal` — the goal in one or two sentences, and the source it came
   from with its confidence.
2. `## On track` — the work that serves the goal, grouped by area, with
   load-bearing detours named alongside what each unblocked.
3. `## Drift` — off-goal commits and uncommitted changes, where the
   excursion started, and the pattern behind it; or that there is none.
4. `## Gap` — criteria the goal asks for with nothing on the branch
   addressing them; or that there are none.
5. `## Realign` — the recommended correction and the reasoning, followed
   by the alternatives that were not recommended.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
⚠ Drift: the login rate limiter was refactored before the throttling work started.

## Goal

- Ship password-reset email throttling. The goal came from the ticket's acceptance criteria.

## On track

- Throttle config and the per-address counter in the reset handler.

## Drift

- Four commits restructure the login rate limiter. Off-goal work started at the "Extract limiter interface" commit.
- Pattern: each throttling change pulled in a limiter change first.

## Gap

- The ticket asks for a test of the throttled response; nothing on the branch covers it.

## Realign

- Split the limiter commits to a follow-up branch and finish the test here. The refactor is sound but belongs in its own review.
- Not recommended: widening the goal to include the refactor.

1. Finish the gap
2. Split the off-goal work to a follow-up
3. Drop the off-goal work
4. Widen the goal to match
```

End with an `ask-user-choice` panel offering the correctives as actions
— finish the gap, split the off-goal work to a follow-up, drop it, widen
the goal to match the work — so the user can choose without composing a
command. Skip the panel only in plan mode; without the tool, end with
those options as numbered lines.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
