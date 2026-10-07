# A worked example: sweeping one plugin's prompts

Read this only to see what a finding looks like end to end: the prompt
people typed, the verdict, and the edit it became. The catalog here is
invented: a plugin `tidy` with two skills, `tidy:clean` (removes stray
files) and `tidy:dedupe` (merges duplicate files).

Contents:

- The ask
- Finding one: an unnamed procedure
- Finding two: a continuation
- Rejected: a recurring preamble
- Rejected: a constraint already written

## The ask

Scope a sweep to `tidy`: mine the prompts around its skills, find what
people retype, and bring it upstream as a default, a reference, an
argument, or a new skill.

## Finding one: an unnamed procedure

Evidence: the same procedure retyped across sessions and never worded the
same way twice. List what is in a folder, group files by age, move the
oldest group to an archive folder, write a one-line manifest of what moved.
None of the retypings named a skill, so counting slash invocations found
zero; only the no-invocation corpus showed it.

Verdict: absent. `tidy:clean` deletes and `tidy:dedupe` merges; nothing
archives.

Edit: a new skill `tidy:archive` with three ordered steps (list, move,
manifest), a dry-run default, and a manifest stored outside the working
tree.

## Finding two: a continuation

Evidence: after `tidy:dedupe` ran, prompts asked for the removed duplicates
to be listed in a report.

Verdict: absent as a terminal step. The skill merged files and stopped
without saying which ones.

Edit: end `tidy:dedupe` with a list of merged files and an opt-out flag.

## Rejected: a recurring preamble

A preamble naming a preferred shell and a log directory recurred after the
skill name. It applies to any long task, not this plugin, so no argument
was proposed.

## Rejected: a constraint already written

Prompts kept saying never to delete without listing first. `tidy:clean`
already said so. Repetition alone made that an invariant a new skill had
to preserve, not a gap, so it needed no edit.

A finding that cannot show both halves, the prompt and the edit, is not
ready to land.
