---
type: llm
focus: last_message
---
The reply flags the "Notes" heading as needing renaming or removal, since it names no step or decision.
The reply flags the filler paragraph explaining why formatting is important, since removing it changes nothing the agent does.
The reply flags the "helper" skill name and/or the vague description as needing a rewrite, since neither states in a user's literal words when to invoke the skill.
The reply presents its cuts as a ledger, ie. one entry per removed or changed line with a reason, rather than only a rewritten file with no explanation.
The resulting body preserves both literal flags and their mode meanings: `--check` forbids modifying the file, and `--fix` applies fixes. The table may become prose or bullets, but default apply behavior does not replace explicit `--fix` support. Ledger quotations and removed-only diff lines do not count as preservation.
The reply does not infer that mode flags are unavailable merely because the body has no argument placeholder. It may recommend a clearer description, but does not claim measured matching, exclusion, or improved routing without a host evaluation. A read-through supports only a stated hypothesis or textual ambiguity.
