# Weave consensus map

Shared by `ask` and `review`; `<session_dir>` is as in `ensemble-core.md`.

Where lanes disagree, the variance is information. Adjudication decides what is
true (evidence wins); the consensus map reports how confident the ensemble is,
and must never be silently adjudicated away. For commands that merge findings
or claims (`ask`, `review`), write the per-item map to `pass-NNNN/consensus.md`
with blind labels while adjudicating. It does not apply to `brainstorm`, where
independent diversity is the product.

Classify each lane per item as agree (asserts it or a compatible position),
dissent (an incompatible position, including "not an issue"), or silent. Count
over the M lanes that produced an output. On cascade-escalated runs the Skeptic
and Builder were primed with the fired triggers, so an item restating a fired
trigger counts those two lanes only.

- unanimous: M of M agree.
- majority: more than M/2 agree, with a dissenter or a silent lane.
- split: no position above M/2, including 1-1 conflicts at M = 2.
- single: one lane agrees, the rest are silent.

Dissent and silence differ: a single uncontested item outranks a split one.
Consensus orders and labels; it never overrides verification, so a unanimous
claim the code contradicts is still `false`. Skip it when M = 1.

Surface it in the output:

- review: every verified finding carries a tag (`consensus 3/3`,
  `consensus 2/3`, `consensus 1/3 (uncontested)`). Within a severity band, order
  unanimous-verified, majority-verified, single-verified, then unverified.
  Split findings that verification could not settle appear under Reviewer
  Disagreements with both positions and each side's evidence; they are never
  dropped. Once verification settles a dispute, retain its vote history in
  `consensus.md` and render its conclusion only in the result section that owns
  that status.
- ask: the Disagreements section renders every split and
  majority-with-dissent item: both positions, which was adopted, and the deciding
  evidence, or "unresolved, both positions retained".
