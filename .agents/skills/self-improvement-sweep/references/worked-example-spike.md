# A worked example: sweeping one plugin's prompts

A sweep of one plugin's usage, read in one sitting, produced the spike
ratchet skill and three edits to the spike probe and bakeoff skills.
The method matters more than the outcome: read the text people type
around an invocation, name the gap, and land an edit that shows both
the prompt and the change.

Contents:

- The ask
- What the corpus held
- Reading it wrong, first
- Finding one: the cycle had no name
- Finding two: grafts landed without being run
- What was rejected
- What this shows

## The ask

The request scoped a sweep to one plugin: mine prompts that mention its
skills, find what people retype around them, and bring it upstream as a
default, reference, argument, or new skill, with every added line
checked for bloat. The text typed around an invocation is the skill's
gap, stated by the person who hit it.

## What the corpus held

One procedure, retyped seven times, never worded the same way twice:
try the idea for real, note what fought back, run a bakeoff when
approaches differ, pick the winner plus grafts, spike again, repeat,
keep planning notes. Four retypings were one sentence, three were a
numbered list.

- The planning-notes step went missing most often, and it is the reason
  to run rounds at all.
- None of the seven named a skill the way either host invokes one, so
  counting slash invocations found zero. The procedure with the
  strongest case for a skill was invisible to invocation counting.
- Every genuine retyping came from one host. A per-host count that had
  not removed the sweep's own reflection (sessions quoting the prompt
  back) would have reported the cycle as evenly split.

## Reading it wrong, first

Two traps looked like measurements:

- A search with a low result limit returned a bounded result. Forty
  results came back against sixty-nine matches, and only the `state`
  field said `bounded`. Re-running with a high limit returned
  `complete`. The deduplicated record count, the raw match count, and
  the count after the sweep wrote the phrase into its own session were
  three different numbers.
- Project attribution reported every occurrence in a single repository,
  which reads as one project's quirk. All of them were sessions working
  on the sweep itself. The genuine evidence came from a host that
  records no project field, so its spread had to be read off the
  prompts, which named the several ports they were written for.

Check the completeness field, and check who produced each match, before
scoring a finding.

## Finding one: the cycle had no name

Category: unnamed procedure, typed instead of an invocation. Verdict:
absent. Probe answered whether one path works and bakeoff answered
which of several is best; nothing answered what the design should be.

Every retyping ended with a stop condition that could not be evaluated,
so a human had to decide when to quit. The new skill replaced it with
three falsifiable, ordered stops: thrashing (every stumbling block was
already recorded in an earlier round), converged (a round surfaced
none), and capped (the round limit ran out). Thrashing is the one the
retypings could not express: more spiking cannot settle the question.

The dropped planning notes became a ledger stored outside the working
tree, because each round stashes and cleans its own tree.

The probe skill gained the concept the cycle branched on, stumbling
blocks: places the approach itself fought back. A stumbling block is
neither a marked shortcut nor an out-of-scope adjacent problem. The
probe reports them even on success, because a path that worked while
fighting the whole way is the case for a bakeoff.

## Finding two: grafts landed without being run

Category: continuation, typed after an invocation, session after
session. People asked for the selected graft to be proven in a probe
and for the winner plus grafts to be confirmed before landing, and one
prompt named the defect outright: a graft from a losing contender that
nobody had confirmed a user wanted.

Verdict: absent as a named handoff, and worse as a mechanic. The
bakeoff judged grafts on paper, proved the winner's stash without them,
and replay would land the combination anyway. The edits marked grafts
as unproven in combination, re-ran the proving check before each replay
item that carried one, and added a panel option to probe the grafted
winner.

## What was rejected

A preamble naming study directories, linters, and an adversarial
reviewer recurred after the skill name. It applies to any long task, not
this plugin, so the sweep proposed no argument for it.

A constraint typed often enough to look like a finding, that spike
mutates code but never commits it, was already written into both
skills. Repetition alone did not make it a gap. It made an invariant
the new skill had to preserve, which needs no edit.

## What this shows

The useful output of a sweep is a prompt and the edit it became, side
by side. Seven retypings justified one new skill, one sentence about
provenance justified three hunks in an existing one, and a recurring
preamble justified nothing. A finding that cannot show both halves is
not ready to land.
