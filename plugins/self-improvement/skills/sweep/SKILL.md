---
name: sweep
description: "Use when mining prompt history to rank skill usage, count how often each skill runs, find never-invoked skills, or improve repeated instructions."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[<plugin|plugin:skill>...]"
user-invocable: true
---


# `/self-improvement:sweep`

Your prompt history records what you did, not what the skills were
designed to do. Where the two disagree, the prompts are right. This
skill reports where the catalog loses to them: instructions retyped
around a skill, follow-ups appended because a skill stopped early, and
procedures run by hand because no skill exists.

It changes nothing: no edits, no commits, no pushes. Its output is a
ledger of findings with their evidence. `/self-improvement:apply` acts
on it.

## Two shapes carry the signal

**Typed around an invocation**: the prompt names a skill and adds
something. The addition is the skill's gap. The remedy is inside that
skill.

**Typed instead of an invocation**: a procedure restated near verbatim,
session after session, with no skill named. The remedy is a new skill.

A pattern that is neither is usually not a finding. A worked example of
the whole pass is `../../references/worked-example-spike.md`.

## The evidence bar

A finding needs repetition, spread, and currency: several occurrences,
across more than one project or ecosystem, in the era of the catalog
you are about to change. One project's friction is that project's
quirk; one dead era's friction is history.

Every window is anchored to a date the catalog supplies, never to one
chosen because it flatters a number:

- A pattern typed around an existing skill is windowed on that skill's
  birth date. That separates a discoverability gap from a rule people
  read and ignored.
- A pattern typed with no skill named is windowed on the era boundary
  Phase 0 fixes. The question is whether the typing is still happening.
- The Usage ranking uses the era boundary, so retired skills do not
  outvote live ones.
- The supersession check uses the successor's birth date.

A skill too young to have a handful of invocations cannot clear
repetition however the window is drawn. Report the window and its
anchor beside every ratio.

Report ratios, not counts. The same "instructions appended to
`changelog`" evidence means "make this a checked gate" at half of all
invocations and "offer an opt-out default" at a fifth.

Read `../../references/detecting-invocations.md` before counting: it
covers the two invocation channels, renames, supersessions, truncated
queries, and query cost.

## What counts as a signal

Around an invocation:

- **Paste**: the same preamble reappears after the skill name
  (directories, tool preferences, a quality bar, a constraint). Becomes
  a default, a resolved input, or a reference example.
- **Continuation**: the next prompt asks for a step the skill stopped
  short of. Becomes a terminal step with an opt-out, or a named
  handoff.
- **Override**: the argument re-scopes the target (a set where the
  skill assumed one, a different target type, a state it appeared to
  refuse). Becomes an argument, or detect-and-echo.

Without an invocation:

- **Unnamed procedure**: a multi-step instruction restated with a slot
  or two varying. Only this category may propose a new skill, because a
  skill costs a marketplace entry, a README row, and a description that
  must survive the collision check. "The usual" or "same as last time"
  is stronger evidence than raw repetition.
- **Host asymmetry**: the same skill measured per host, then
  differenced. The finding is the gap. A near-empty host channel means
  the extraction does not fit that host.
- **Correction**: a prompt shortly after an invocation saying the agent
  did the wrong thing. Highest severity, weakest attribution: binding a
  correction to a skill is same-session adjacency. State the anchoring
  method and window, and confirm against the transcript before
  proposing anything expensive.

## A superseded skill is not a gap

Check this before the verdicts. A predecessor keeps its invocations
forever and stops earning new ones when a successor ships, so its ratio
stays high while its current usage is zero.

A full record with an empty recent half is the symptom. Name the
successor and confirm it shows the mirror image: empty until its birth
date, then holding the traffic. Only then is the pattern history; say
so and move on.

A predecessor that went quiet with no sibling picking up its work is
abandoned, not superseded. That is a live finding.

## The three verdicts

For every surviving pattern, ask what the skill already says:

1. **Absent**: the skill never covered it. Propose it.
2. **Present and binding**: the pastes stopped after the skill started
   saying so. Solved.
3. **Present but not binding**: the skill says it and people keep
   retyping it. The most-pasted constraints are usually already
   written in the skill they concern, so reading alone never reaches
   this verdict.

Reach the third by dating the rule and splitting the evidence around
it.

```console
git log --follow --format='%h %ad' --date=short -S '<phrase from the rule>' -- <path to SKILL.md> | tail -1
```

`--follow` keeps a rename from dating every phrase to the rename. `tail
-1` returns the rule's introduction, because `-S` lists newest first.

A paste rate that did not drop after that date proves prose guidance
failed. The remedy is a checked output gate or a resolved-and-echoed
value, never another sentence. A rate that dropped means it worked.

The same split separates a **trust gap** (the skill performs a behavior
but never announces it; echo it) from a **capability gap** (it never
performs it).

## `$ARGUMENTS` contract

Non-flag text narrows the sweep to named plugins or skills. Empty
sweeps the whole catalog of the repository you are in; outside a skill
repository, ask what to sweep.

## Phase 0: Inventory, rename map, and birth dates

1. List the catalog: every `plugins/*/skills/*/SKILL.md`, its name, and
   whether it sets `disable-model-invocation`.
2. Build the rename map before counting, so a renamed skill's old
   invocations are summed in.

```console
git log --diff-filter=R --name-status --format='%h %s' -- 'plugins/*/skills/*'
```

   Read commit subjects too, for renames the detector scored below its
   threshold and for skills replaced by a different set.

3. Date every skill, one path per run. `--follow` requires a single
   file and silently returns the oldest commit touching any skill when
   given a glob.

```console
git log --follow --format='%ad' --date=short -- <path to SKILL.md> | sort | head -1
```

   Birth dates cluster on the days the catalog changed shape. A cluster
   holding at least a tenth of the catalog is a rebuild; smaller ones
   are batches of arrivals. Take the most recent rebuild as the era
   boundary, and report it with the runners-up so the next sweep can
   disagree.

   If the era's leading skill holds too few invocations to form a
   ratio, rank all-time only and say so.

## Phase 1: Count every skill

Extract both channels per `../../references/detecting-invocations.md`,
union them, and sum across renames. Keep the timestamp on every
occurrence that has one, because the era split cannot be recovered
after a query collapses to name and count. Confirm the sweep completed
before applying any threshold.

Split the counts on the era boundary and carry both halves. Only the
slash channel carries a usable date, so the era ranking comes from one
channel and must say so: a skill the model reaches for on its own is
undercounted there.

State what the count assumes about the corpus. An archived or reclaimed
transcript store comes back clean, complete, and wrong.

Run one broad exhaustive query, save the raw JSON, and re-slice it
locally.

## Phase 2: Cluster

Group the text around each invocation by shared phrasing and sort each
cluster into paste, continuation, or override by what its tail does.
Cluster the no-invocation corpus separately, where near-verbatim
repetition, not frequency, is the signal.

## Phase 3: Verdicts

Drop superseded clusters, then run the three verdicts on each cluster
that clears the evidence bar. Record the ratio, spread, window, and the
mechanic that produced the verdict. Where a finding has two plausible
answers, record both shapes and let the proposal say so.

## Output contract

Write the report per `../../references/prose-rules.md`.

1. Hero block (1-3 lines): `N findings across M skills` plus how much
   of the corpus the search reached.
2. `## Usage`: the catalog ranked twice by invocation count, all-time
   and current-era. Channels unioned, renames summed. Name never-invoked
   skills as that, each with its age.
3. `## Findings`: one entry per pattern: category, ratio and
   denominator, window and anchor date, spread, verdict with its
   evidence, and the change class it implies. Quote one representative
   prompt, trimmed.
4. `## Not proposed`: clusters that failed the evidence bar, and which
   leg they failed. Never omitted.
5. `## Corpus`: what was searched, what completed, what the count
   assumes, and the era boundary with the clusters it was chosen over.
   Close with the ledger key: the catalog's `HEAD` and a digest of the
   finding set. `/self-improvement:apply` recomputes it, and a mismatch
   means the catalog moved since the sweep.
6. End with an `AskUserQuestion` panel: hand the ledger to
   `/self-improvement:apply`, narrow the sweep and rerun, or stop. In a
   non-interactive run, record the options and stop.

The ledger may quote prompts with absolute paths, hostnames, and client
names. A `SKILL.md`, commit, pull request, or issue may not.
