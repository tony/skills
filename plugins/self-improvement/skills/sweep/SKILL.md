---
name: sweep
description: >-
  Use to measure how a skill catalog is actually invoked: mine local
  agent prompt history with agentgrep for per-skill invocation counts
  across hosts and projects, plus the arguments recorded alongside
  them. Triggers on "sweep the corpus", "mine my prompt history",
  "rank my skills by usage", or "which skills never get invoked".
  Reports usage evidence; edits nothing.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[<plugin|plugin:skill>...]"
user-invocable: true
---


# `/self-improvement:sweep`

The corpus of your own prompts records what you actually did, not what
the skills were designed to do. Where those two disagree, the prompts
are right.

This skill reads that record and reports where the catalog is losing
to it: instructions retyped around a skill that should have been in
it, follow-ups appended because the skill stopped a step early, and
procedures run entirely by hand because no skill exists for them.

## This skill changes nothing

No edits, no commits, no pushes. Its whole output is a ledger, and
acting on it is `/self-improvement:apply`'s job. That is also why this
one is safe to route to on the model's initiative and the apply half
is not: reaching for a sweep costs a report.

## Core thesis

Two shapes carry almost all the signal, and they point opposite ways.

**Typed around an invocation** — the prompt names a skill and then
adds something. That addition is the skill's gap, stated by the person
who hit it. The remedy is inside the skill that was already invoked.

**Typed instead of an invocation** — a procedure restated near
verbatim, session after session, with no skill named anywhere. The
remedy is a skill that does not exist yet.

A pattern that is neither is usually not a finding.

A worked example of the whole pass — the prompts that were mined,
the verdicts, and the edits they became — is
`../../references/worked-example-spike.md`. It was run by hand
before this skill existed.

## The evidence bar

A finding needs repetition, spread, **and currency**: several
occurrences, across more than one project or ecosystem, in the era of
the catalog you are about to change. One project's friction is that
project's quirk. One dead era's friction is history. Proposing a
catalog change from either is how a catalog gets bloated.

Currency and repetition pull against each other, and that tension is
what stops the window from being drawn wherever the numbers look best.
A skill young enough to have accumulated a handful of invocations
cannot clear repetition however the window is drawn — two of three is
not a ratio — and a finding that needs a window narrower than its
skill's lifetime to look large is not a finding.

Report **ratios, not counts.** Every useful finding here is a
denominator away from its opposite: the same "instructions appended to
`changelog`" evidence says *make this a checked gate* at half of all
invocations and *offer it as an opt-out default* at a fifth. A bare
numerator cannot tell those apart, and a ledger full of bare
numerators leaves the reader unable to sort majority behavior from a
5% tail.

Getting the denominator right is the hard part, and its traps have
measured consequences. Read `../../references/corpus-queries.md`
before counting anything: it covers the two invocation channels and
why either alone is wrong, why renames split a skill's history and why
supersessions split it the other way, how to tell a truncated query
from a real absence, and what one exhaustive query costs.

## What counts as a signal

Around an invocation, sorted by how the tail behaves:

- **Paste** — the same preamble reappears after the skill name:
  reference directories, tool preferences, a quality bar, a
  constraint. Changes *how* the skill works. Becomes a default, a
  resolved input, or a reference example.
- **Continuation** — the next prompt asks for a step the skill stopped
  short of. Changes *what comes after*. Becomes a terminal step with
  an opt-out, or a named handoff.
- **Override** — the argument re-scopes the target: a set where the
  skill assumed one, a different target type, a state it appeared to
  refuse. Changes *what it runs on*. Becomes an argument, or
  detect-and-echo.

Without an invocation:

- **Unnamed procedure** — a multi-step instruction restated with only
  a slot or two varying. Only this category may propose a new skill,
  and the bar is high because a skill costs a marketplace entry, a
  README row, and a description that must survive the collision check.
  Someone asking for "the usual" or "same as last time" is trying to
  name something that has no name; that is stronger evidence than raw
  repetition.
- **Host asymmetry** — the same skill measured per host, then
  differenced. The finding is the gap, not either count. A host whose
  channel comes back near-empty means the extraction does not fit that
  host until proven otherwise, never that the host has no users.
- **Correction** — a prompt shortly after an invocation saying the
  agent did the wrong thing. Highest severity, weakest attribution:
  binding a correction to a skill is same-session adjacency, a
  heuristic. State the anchoring method and its window in the ledger
  rather than presenting adjacency as attribution, and confirm against
  the transcript before proposing anything expensive.

## A superseded skill is not a gap

Check this before the verdicts, because it disqualifies the pattern
rather than judging it. A predecessor keeps its invocations forever and
stops earning new ones the day a successor ships, so its ratio stays
high while its present-tense usage is zero. Split it on the successor's
birth date: a full record with an empty recent half is **superseded**,
and every pattern around it is a historical record rather than a gap.
Say so and move on. The remedy already shipped, and a handoff proposed
here would point a skill nobody invokes at the one that replaced it.

## The three verdicts

For every pattern that survives that check, ask what the skill already
says. There are three answers, and the middle one is the trap:

1. **Absent** — the skill never covered it. Propose it.
2. **Present and binding** — the skill covers it and the pastes stop
   after it started saying so. Solved; the residue is noise.
3. **Present but not binding** — the skill says it and people keep
   retyping it anyway.

The third verdict is unreachable by reading alone, and skipping it
throws away the best findings in a typical sweep: the most-pasted
constraints are usually already written in the skill they concern. Get
to it by dating the rule and splitting the evidence around it.

```console
git log --follow --format='%h %ad' --date=short -S '<phrase from the rule>' -- <path to SKILL.md> | tail -1
```

`--follow` because a rename otherwise dates every phrase in the file
to the rename, which is the same history-splitting this skill builds a
rename map to avoid. `tail -1` because `-S` lists newest first, and
`-1` would return the rule's latest edit rather than its introduction.
`--reverse` is not the fix: `-n` applies before the reversal, and
`--follow --reverse` returns nothing.

Compare the paste rate before that date against after. A rate that did
not drop is proof that prose guidance failed, and the remedy is a
checked output gate or a resolved-and-echoed value — never another
sentence saying the same thing. A rate that dropped means it worked.

The same split separates two findings that look identical: a behavior
the skill performs but never announces is a **trust gap**, fixed by
echoing it; a behavior it never performs is a **capability gap**.

## `$ARGUMENTS` contract

Non-flag text narrows the sweep to named plugins or skills. Empty
sweeps the whole catalog of the repository you are in; outside a skill
repository, ask what to sweep rather than guessing.

## Phase 0: Inventory, rename map, and birth dates

1. List the catalog: every `plugins/*/skills/*/SKILL.md`, its name,
   and whether it sets `disable-model-invocation`.
2. Build the rename map before counting. A renamed skill keeps its old
   invocations under its old name, and summing across every name a
   skill has had is the difference between a real count and an 82%
   undercount.

```console
git log --diff-filter=R --name-status --format='%h %s' -- 'plugins/*/skills/*'
```

   Read commit subjects too, for renames the detector scored below its
   threshold and for skills replaced by a different set rather than
   renamed. The successor inherits none of the history either way.

3. Date every skill. A rename map says which names are one skill; it
   cannot say when a behavior first became reachable, and months a
   skill did not exist for are nobody's denominator.

```console
git log --follow --format='%ad' --date=short -- <path to SKILL.md> | tail -1
```

   Birth dates that cluster on a single day mark a structural change to
   the catalog rather than one skill's arrival. That day is the
   boundary the census reports either side of.

## Phase 1: Census

Extract both channels per `corpus-queries.md`, union them, and sum
across renames. Confirm the sweep completed before applying any
threshold — a bounded run and a genuine zero look identical.

Then split the census on the boundary from Phase 0 and carry both
halves forward. A corpus that accumulated across a catalog rebuild is
mostly a record of skills that no longer carry the behavior, and the
older half can outweigh the newer one by enough to decide the ranking
on its own.

State the corpus assumption in the report: an archived or reclaimed
transcript store reports a clean, complete, wrong census, so the
completeness gate is necessary and not sufficient.

Budget deliberately. One exhaustive query reads the whole corpus, so
fan out per skill and the sweep costs hours. Run one broad query, save
the raw JSON, and re-slice it locally for every question after that.

## Phase 2: Cluster

Group the text that surrounds each invocation and cluster it by shared
phrasing. Sort each cluster into paste, continuation, or override by
what its tail does. Cluster the no-invocation corpus separately, where
near-verbatim repetition — not frequency — is the signal.

## Phase 3: Verdicts

Drop the superseded clusters first, then run the three verdicts against
each one that clears the evidence bar, and record the ratio, the
spread, the window that denominator covers, and the mechanic that
produced the verdict.

Window each finding against the birth date of the skill that covers
it, not against one date for the whole sweep. Skills arrive on
different days, and measuring a hand-typed procedure against the day
its skill shipped is the difference between *nobody knows this exists*
and *this shipped and the typing stopped*.

Where a finding could be answered two plausible ways, do not judge it
here — record both shapes and let the proposal say so.

## Output contract

1. Hero block (1–3 lines): `N findings across M skills` plus the
   corpus coverage the census actually achieved.
2. `## Usage` — the catalog ranked twice by real invocation count,
   all-time and current-era, because a skill can lead the first and be
   absent from the second. Channels unioned and renames summed. Name
   the never-invoked ones as unranked rather than as dead, each with
   its age: zero invocations in three weeks and zero in six months are
   different facts, and only the second is about the skill.
3. `## Findings` — one entry per pattern: category, the ratio and its
   denominator, the window that denominator covers, spread, the
   verdict with the evidence that produced it, and the change class it
   implies. Quote one representative prompt, trimmed.
4. `## Not proposed` — clusters that failed the evidence bar, and
   which half they failed. This is the section that keeps the catalog
   small, so it is never omitted.
5. `## Corpus` — what was searched, what completed, and what the
   census assumes. Close it with the ledger key: the catalog's `HEAD`
   and a digest of the finding set. `/self-improvement:apply`
   recomputes that key, and a mismatch means the catalog moved since
   the sweep and the ledger describes a picture that no longer holds.
6. End with an `AskUserQuestion` panel: hand the ledger to
   `/self-improvement:apply`, narrow the sweep and rerun, or stop. In
   a non-interactive run, record the options and stop.

Evidence is quoted here and stripped from anything that lands. Prompts
carry absolute paths, hostnames, and client names; the ledger may show
them, a `SKILL.md`, commit, pull request, or issue may not.

## What this is not

- **Not a description grader.** `scripts/skill_evals.py route` ranks a
  prompt against the live catalog and `check` enforces the collision
  ceiling and description limits. Mined prompts are the ground truth
  those were missing — feed them in and report disagreements rather
  than inventing a second opinion about routing.
- **Not a prose auditor.** A finding with no usage fact behind it is
  `/lean:tighten`'s or `/slop:scan`'s work; say so and route there.
- **Not a bakeoff.** When a finding has two plausible shapes, that is
  `/spike:bakeoff`.
- **Not a diff against the last sweep.** Re-derive from the corpus and
  report standalone. A sweep that reports itself as a delta against
  its own previous run is the failure `/double-check:double-check`
  exists to prevent.
- **Not a census of one project.** Reading a single project's history
  to explain the branch in front of you is `/situate:situate`, which
  reconciles against the repository and wins there.
