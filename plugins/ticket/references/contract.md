# The content contract

Contents: Past (the cost-to-relearn filter); Present (nothing that rots); Future (invariants and intent); The rule that catches the worst failure; Body rules; Credentials; Unverified.

Every body this plugin writes follows three rules, one per tense, the same
for a GitHub issue, a Linear project, a Confluence page, and a merge request.
How much of each an object carries is in `altitude.md`; how a renderer
expresses a reference is in the provider's file, indexed in `resolve.md`.

## Past: the cost-to-relearn filter

Carry what cannot be recovered from the repository. Drop what can.

Keep a measurement together with the conditions that produced it. A number
without its conditions is not evidence, it is folklore, and the next person
either trusts it wrongly or re-runs it.

Keep a dead end when someone would otherwise retry it, and say why it died.
"We tried a worker pool and it lost to serial early termination once pool
startup was counted" saves a week. "We considered concurrency" saves nothing.

Keep a retracted number, with what was actually measured. A figure that
circulated and turned out to be a COUNT-only query against a contentless
index is worth more written down than deleted.

Keep an upstream constraint, a platform quirk, or a decision that closed off
an obvious-looking road.

Drop anything a reader recovers by opening the file, reading the log, or
looking at the diff. File sizes. What got renamed. Which module was split.
That a draft was long before it was short.

Drop the sequence of hypotheses that led to the finding, and revisions that
happened while drafting: carry the final form, not the move.

The test: **if this were deleted, would the reader have to redo work to get
it back?** Yes, keep it. No, cut it.

Quote a durable source verbatim and pin the link. Paraphrase a conversation;
there is nothing to pin, and inventing a citation is worse than having none.

## Present: nothing that rots

A reference must survive the next refactor and must not create side effects
you did not intend.

Do not write insertion counts, file counts, test counts, or line counts. Do
not write "as of <date>". Do not link `blob/main`. Do not put a line anchor
on an unpinned ref. Name the symbol, the path, or a pinned permalink instead.

Counts, dates, and hashes stay when they *are* the evidence: a benchmark
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

Referencing is not free: it posts a visible event onto the thing you named,
welcome on a sibling issue and unwelcome on bot traffic or a stranger's
repository. An explicit link is not the quiet form; trackers describe it as
manual linking.

**How to suppress it is provider-specific, and it is rarely the link
form.** GitHub documents a host swap. GitLab documents nothing short of
escaping the reference, which also removes the link. Some objects are
not mentionable and fire nothing. Read the provider file; do not generalize
one tracker's answer onto another.

Each provider file states its auto-detected forms and which of them fire a
backreference. `ref_form.py` (in the plugin's `scripts/`) applies the rules: give it
the provider, whether the target is in the same container, and the intent
(`--notify` or `--quiet`), and it prints the form or exits 1 when the provider
documents no form for that intent. `#N` on
its own is not evidence of which tracker you are in.

### Mentions

Never `@mention` anyone in a generated body, including mentions in a body
being rebuilt. A mention subscribes and notifies the person, and re-saving a
body can send it again.

## Future: invariants and intent

A body states what it is for and what would make it worthless. It does not
pre-commit the implementation.

**Invariants.** A handful at most, each passing one test: *if this is
violated, is the work pointless, or is a neighbour broken?* Anything that
fails the test is not an invariant.

Write an invariant only from a constraint the input states, in the input's
own nouns and figures, adding no clause the input lacks ("resume on their own",
"never slower"). An item that only names a technical choice is Intent, not
an invariant. When the input states no constraint, leave Invariants out and
record an Unverified entry.
Never suggest a candidate invariant, in the body or the reply.

Say plainly that the invariants are the non-negotiable part and everything
else is open; otherwise a reader treats every constraint as load-bearing and
the ticket ends up dictating a storage engine.

**Intent.** Everything else, labelled non-binding. The current thinking, the
direction being leaned toward, what is still undecided. Intent is where a
preference goes so that it informs without governing. A figure or technical
choice (an algorithm, a cap, a pattern, a target number) the input gives goes
here as given, with no clause on what it does for the work. It never appears in
the title, Outcome, or Summary, even when the input's title names it, and
never as a direction built from it ("lower latency", "faster"). The title and
Outcome (Summary, for a work item) state the result and name every scope item
the input lists, in its nouns, the largest included; a chosen mechanism appears
there only by its role ("the search backend", never the engine). When the input
states only mechanisms, the Summary names the subject and nothing more, and
keeps the input's verb.

**Not doing.** Explicit non-goals. Cheaper to write than to re-litigate.

No checkbox definition-of-done. No measurement threshold as a gate; a
threshold is a number, and a number in the future tense is a guess. If a
performance floor is existential, it is an invariant, stated as what a
user notices.

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

## Body rules

These apply to every body, to the user's request when drafting and to the
item's own text when rebuilding.

1. Use the input's nouns, figures, and verbs, close to its sentences. Add
   nothing it does not give: impact, motivation, a quality adjective,
   placement, scope, an expected-behavior sentence, or a rule. A
   symptom-only report gets the symptom restated and nothing more.
2. Report no reproduction status, cause, or vendor requirement the input or
   the provider file did not state. "Repro steps: not provided" is the whole
   fact. A defect title names the symptom as reported, without a cause.
3. State each fact once, in the section that owns it.
4. State facts about the work, never advice about the document. Write the
   link, or record an Unverified entry.
5. Do not mention the revision, and use no time-relative words ("currently",
   "for now"). Use American spelling.
6. Headings inside the body are `###`, so they nest under the reply's body
   heading.
7. Flag a reproduction step that pipes a remote script into a shell or
   deletes data, beside the step.

## Credentials

A credential-shaped string in the input (the scan reports it as `secret`) is
redacted in every body, quote, and reply (`scan_body.py --mask` writes the
redacted text), never printed, and the reply tells
the user to rotate it, since it has already been shared.

## Unverified

Record an Unverified entry (wording in `replies.md`; under Missing for the first
two in a rebuild) when:

- the input states no constraint, so Invariants is left out;
- a defect has no reproduction steps;
- the work needs a design the input does not link;
- the user's words and the project's rules do not settle type, labels, or priority;
- the duplicate search could not include closed items, or no tracker was reachable;
- the input includes an image;
- a readback could not be saved to a file;
- a provider default could not be confirmed against the instance.
