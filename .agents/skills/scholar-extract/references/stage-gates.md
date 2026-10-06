# Stage gates

Each stage has one exit condition. A stage may not hand off until its gate
passes, and a failed gate is reported rather than worked around.

The gates exist because the stages do not call each other — they communicate
through files. A stage that hands off a malformed artifact fails somewhere
downstream, where the cause is no longer visible.

## gather

Every source in `sources.jsonl` has a resolved ref and, for a git source, the
`commit` that ref pointed at, and every source recorded as not read has a
stated reason in `why`.

An unresolved ref means a citation cannot be pinned later. A missing `commit`
means `verify` cannot tell a moved tag from an unmoved one. An unexplained
omission means the study cannot state its own coverage boundary.

## extract

Every row in `terms.jsonl` has a non-empty `definition` and at least one entry
in `cites`. `term-metrics.py <study> --check-terms` lists the rows that fail.

A term with no definition is a word the corpus happens to contain. A
definition with no citation is the analyst's summary of the corpus, which is
the thing this pipeline exists to avoid producing.

## distill

Every type has a discriminator, and `term-metrics.py` reports no orphans: a
term with no parent, or a parent that is neither another term nor `root`, is an
orphan.

## contest

The analyzer has run, every finding it produced has a recorded verdict in
`evidence/contested.md`, and the last round produced no new contested claim.

A finding with no verdict is worse than no finding: it reads as a problem
someone already considered.

## render

The brief gate exits zero:

```console
$ <analyzer> notes/ontology/<subject>/ --check-brief
```

`<analyzer>` is the path to `term-metrics.py`, which ships beside this file.

A non-zero exit means the brief is not renderable yet (exit 2 means the file
is missing). Fix the brief, not the
checker.
