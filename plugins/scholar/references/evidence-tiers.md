# Evidence tiers

Every claim a study makes sits in one of two tiers, and the tier decides what
the claim must carry.

## Structural

*This is-a that. These are the members. This term means this.*

Backed by a pinned citation, per `citation.md`. The reader checks it by
opening the link and reading the quoted lines at the recorded locator.

A structural claim needs no number. For an is-a claim, cite the source's
declaration or definition of that relation. Names alone do not establish it.

A stated role does not prove an exclusive role. Distinct names do not prove
disjoint types, and a docstring does not prove implementation behavior.
Architectural labels and claims that something never happens need their own
evidence; an omitted behavior is unknown, not ruled out.

## Distributional

*How often. How similar. How concentrated. How it changed.*

Backed by a command a reader can paste and the output it produced, both
recorded in `evidence/metrics.md`. The command goes in a `console` block, the
output in the block beneath it.

The measurement must be reproducible from the study's own artifacts or from
the pinned corpus. A number copied from a run nobody can repeat is not
evidence.

Keep a measurement together with the conditions that produced it. A score
without the corpus it was computed over says nothing.

## The closing rule

A claim that fits neither tier does not go in the brief.

Impressions are worth having. They belong in `evidence/contested.md` as
claims that were raised and not settled, where a later round can pick them
up. They may not appear in the brief in the same voice as a claim that
carries its evidence.

Apply the same boundary to the final report: summarizing a study cannot add
claims its evidence does not support.
