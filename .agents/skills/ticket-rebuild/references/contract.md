# The content contract

Every body this plugin writes is governed by three rules, one per tense. The
rules are the same for a GitHub issue, a Linear project, a Confluence page,
and a merge request.

How much of each a given object carries is in `altitude.md`. How a specific
renderer expresses a reference is in that provider's file, indexed in
`hierarchy.md`.

## Past — the cost-to-relearn filter

Carry what cannot be recovered from the repository. Drop what can.

Keep a measurement together with the conditions that produced it. A number
without its conditions is not evidence, it is folklore, and the next person
either trusts it wrongly or re-runs it.

Keep a dead end when someone would otherwise retry it, and say why it died.
"We tried a worker pool and it lost to serial early termination once pool
startup was counted" saves a week. "We considered concurrency" saves nothing.

Keep a retracted number, with what was actually measured. A figure that
circulated and turned out to be a COUNT-only query against a contentless
index is worth more written down than deleted, because deleting it does not
delete it from anyone's memory.

Keep an upstream constraint, a platform quirk, or a decision that closed off
an obvious-looking road.

Drop anything a reader recovers by opening the file, reading the log, or
looking at the diff. File sizes. What got renamed. Which module was split.
That a draft was long before it was short.

Drop the sequence of hypotheses that led to the finding. The reader needs
what reproduces it, not the search that found it.

Drop revisions that happened while drafting. A position that moved during a
conversation was never published; carry the final form and do not narrate the
move.

The test: **if this were deleted, would the reader have to redo work to get
it back?** Yes, keep it. No, cut it.

Quote a durable source verbatim and pin the link. Paraphrase a conversation —
there is nothing to pin, and inventing a citation is worse than having none.

## Present — nothing that rots

A reference must survive the next refactor and must not create side effects
you did not intend.

Do not write insertion counts, file counts, test counts, or line counts. Do
not write "as of <date>". Do not link `blob/main`. Do not put a line anchor
on an unpinned ref. Name the symbol, the path, or a pinned permalink instead.

Counts, dates, and hashes stay when they *are* the evidence — a benchmark
result, the version a bug first appeared in, the commit a revert targets.
Evidence is not slop. The difference is whether the number is the claim or
merely decoration on one.

### The two-axis reference rule

How to write a reference to an issue, a commit, or another work item depends
on two questions, in order:

1. **Does the renderer auto-detect it?** If yes, hand-linking fights the
   renderer and reads as noise. Leave it bare.
2. **Does referencing it post a backreference onto the target?** Usually yes,
   and usually the link form does not change that. Wrapping a URL in
   `[text](url)` is still a reference, so it still fires the event.

The second axis is the one people miss, in both directions. Referencing is
not free — it posts a visible event onto the thing you named, which is
welcome on a sibling issue and unwelcome on bot traffic or a stranger's
repository. And the instinct that an explicit link is the polite, quiet form
is backwards: it is exactly the case the trackers describe as manual linking.

**How to actually suppress it is provider-specific, and it is rarely the link
form.** GitHub documents a host swap. GitLab documents nothing short of
escaping the reference, which also removes the link. Some objects are simply
not mentionable and fire nothing. Read the provider file; do not generalize
one tracker's answer onto another.

Each provider file states its auto-detected forms, which of them fire a
backreference, how to avoid it there, and the cross-container form. `#N` on
its own is not evidence of which tracker you are in.

## Future — invariants and intent

A body states what it is for and what would make it worthless. It does not
pre-commit the implementation.

**Invariants.** A handful at most, each passing one test: *if this is
violated, is the work pointless, or is a neighbour broken?* Anything that
fails the test is not an invariant.

Say plainly that the invariants are the non-negotiable part and everything
else is open. A reader who cannot tell which constraints are load-bearing
treats all of them as load-bearing, which is how a ticket ends up dictating a
storage engine.

**Intent.** Everything else, labelled non-binding. The current thinking, the
direction being leaned toward, what is still undecided. Intent is where a
preference goes so that it informs without governing.

**Not doing.** Explicit non-goals. Cheaper to write than to re-litigate.

No checkbox definition-of-done. No measurement threshold as a gate — a
threshold is a number, and a number in the future tense is a guess wearing
a uniform. If a performance floor is genuinely existential, it is an
invariant and it is stated as one, in terms of what a user notices.

The higher the altitude, the fewer invariants and the broader the intent. A
strategic goal that names three invariants has almost certainly encoded
implementation votes as constraints.

## The rule that catches the worst failure

**The body points at the design doc. It never contains it.**

If a paragraph would survive being cut and replaced with a link to an ADR, an
RFC, or a spec, cut it. Two copies of a design means one of them is stale,
and it is always the one in the tracker.

A body that restates a document it links to has stopped being a ticket and
become a fork of that document.
