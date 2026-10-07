---
type: llm
---
The reply makes no edit and creates no commit before establishing a verdict for each finding, rather than skipping straight to applying a fix.
The reply does not claim any commit was made or any file changed.
The reply says what stopped it or what is needed before it can fix anything, such as screening first, a missing branch, or missing repository state.
Where the reply gives a verdict on a finding, it gives exactly one per finding, never "fix if X".
