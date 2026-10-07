# Stage gates

Each stage has one exit condition. A stage may not hand off until its gate
passes, and a failed gate is reported rather than worked around.

## gather

Every source in `sources.jsonl` has a resolved ref and, for a git source, the
`commit` that ref pointed at, and every source recorded as not read has a
stated reason in `why`.

## extract

Every row in `terms.jsonl` has a non-empty `definition` and at least one entry
in `cites`, each with a non-empty `quote`. A `kind: type` row that has a
`parent` is exempt from `cites`, since `distill` writes it and cites the is-a
claim in `evidence/hierarchy.md`; a `type` row with no `parent` must cite, and
any citation a type row carries still needs a quote. `term_metrics.py <study>
--check-terms` lists the rows that fail, including rows with a mistyped field.

## distill

Every type is a `kind: type` row with its discriminator as `definition`,
`--check-terms` still exits zero, and `term_metrics.py` reports no orphans and
no hierarchy cycles. An orphan is a term with no parent, or a parent that is
neither another term nor `root`, or a non-type term parented to `root`; a cycle is a parent chain that returns to
itself, including a term that is its own parent.

## contest

The analyzer has run, every finding it produced has a recorded verdict in
`evidence/contested.md`, no claim is open, and the last round produced no new
contested claim. A run stopped at `--rounds` with a claim still open has not
passed: it reports `⚠ Gate unmet`, never `✓`.

## render

The brief gate exits zero:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-brief
```

`<analyzer>` is `../scripts/term_metrics.py` resolved to an absolute path.

A non-zero exit means the brief is not renderable yet (exit 2 means the file
is missing). Fix the brief, not the checker.
