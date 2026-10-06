# A worked example: sweeping one plugin's prompts

Read this only to see what a finding looks like end to end: the prompt
people typed, the verdict, and the edit it became.

Contents:

- The ask
- Finding one: an unnamed procedure
- Finding two: a continuation
- Rejected: a recurring preamble
- Rejected: a constraint already written

## The ask

Scope a sweep to one plugin's skills: mine the prompts around them, find
what people retype, and bring it upstream as a default, a reference, an
argument, or a new skill.

## Finding one: an unnamed procedure

Evidence: the same procedure retyped across sessions and never
worded the same way twice. Try the idea for real, note what fought back,
run a bakeoff when approaches differ, pick a winner plus grafts, spike
again, keep planning notes. None of the retypings named a skill, so
counting slash invocations found zero; only the no-invocation corpus
showed it.

Verdict: absent. The probe skill answered whether one path works and the
bakeoff skill answered which of several is best; nothing answered what the
design should be.

Edit: a new skill with three ordered, falsifiable stops (thrashing,
converged, capped) and a ledger stored outside the working tree. The probe
skill gained the term the cycle branched on, stumbling blocks.

## Finding two: a continuation

Evidence: after the bakeoff skill ran, prompts asked for the selected graft
to be proven in a probe before landing.

Verdict: absent as a named handoff. The bakeoff judged grafts on paper and
replay landed the combination unproven.

Edit: mark grafts as unproven in combination, re-run the proving check
before each replay item that carries one, and add a panel option to probe
the grafted winner.

## Rejected: a recurring preamble

A preamble naming study directories, linters, and a reviewer recurred after
the skill name. It applies to any long task, not this plugin, so no
argument was proposed.

## Rejected: a constraint already written

Prompts kept saying that spiking mutates code but never commits it. Both
skills already said so. Repetition alone made that an invariant the new
skill had to preserve, not a gap, so it needed no edit.

A finding that cannot show both halves, the prompt and the edit, is not
ready to land.
