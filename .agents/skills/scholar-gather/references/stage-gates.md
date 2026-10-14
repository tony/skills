# Stage gates

Each stage has one exit condition. A stage may not hand off until its gate
passes, and a failed gate is reported rather than worked around.

Contents:

- The study directory
- gather, extract, distill, contest, render: each stage's exit condition

`<analyzer>` is `./term_metrics.py` resolved to an absolute path.
Every command below exits zero when the gate passes and prints one finding
per line otherwise.

## The study directory

`<subject>` is the name of the `--out` directory when one is given; otherwise a
lowercase, hyphenated slug of the target's repository name or document title.
A stage that takes no `--study` or directory uses the only directory under
`notes/ontology/`. With several, ask which; where no question tool exists,
halt and list the names. With none, halt and name the `scholar-ontology` skill.

## gather

Every source in `sources.jsonl` has a resolved ref and, for a git source, the
40-digit `commit` that ref pointed at, and every source recorded as not read
has a stated reason in `why`:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-sources
```

The check also rejects an unknown `locator_kind`, and rows for one `source`
that disagree on `commit` or `locator_kind`.

## extract

Every row in `terms.jsonl` has `schema: 1`, a `kind` from the closed set in
`extract`, a non-empty `definition`, and at least one entry in `cites`, each
with a non-empty `quote` and a `source` that names a row of `sources.jsonl`.
A `kind: type` row that has a `parent` is exempt from `cites`, since
`distill` writes it and cites the is-a claim in `evidence/hierarchy.md`; a
`type` row with no `parent` must cite, and any citation a type row carries
still needs a quote:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-terms
```

Then every quote is tested against its source. A cite into a git source is
read at the recorded commit in that source's checkout, named once per source
as `SOURCE=CHECKOUT` (a single bare `CHECKOUT` serves a one-source study); a
cite into a pasted excerpt stored under the study is searched for in the
excerpt:

```console
$ python3 <analyzer> notes/ontology/<subject>/ \
    --check-quotes SOURCE=CHECKOUT
```

A prose-only study has no checkout: pass `--check-quotes` with no argument to
search its stored excerpts, and `--check-quotations` for `quotations.jsonl`.
A `Misquoted` or `Vanished` line stops the stage. An `Uncheckable` line (a
book, or a source with no checkout) is reported, not failed.

## distill

Every type is a `kind: type` row with a corpus-supported definition and a
cited declaration or membership basis in `evidence/hierarchy.md`. Every
asserted parent relation, equivalence, or disjointness constraint has source
support; `root` remains the special top-level anchor. Review that support
per `evidence-tiers.md`; the analyzer checks table structure, not entailment.

`--check-terms` still exits zero, and so does the hierarchy check:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-hierarchy
```

An orphan is a term with no parent, a parent that is neither another term nor
`root`, or a non-type term parented to `root`. A cycle is a parent chain that
returns to itself, including a term that is its own parent.

## contest

The analyzer has run, every finding it produced has a recorded verdict in
`evidence/contested.md`, no claim is open, and the last round produced no new
contested claim. The first two conditions are checked by the ledger check,
which reads each `Claim:` entry and its `Verdict:`:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-verdicts
```

A run stopped at `--rounds` with a claim still open has not passed: it reports
`⚠ Gate unmet`, never `✓`.

## render

Every assertion in the brief has support in its linked evidence document,
and each link resolves within the study's `evidence/` directory. Review these
per `evidence-tiers.md`; the analyzer does not judge entailment or resolve
every Markdown citation form. Its mechanical gate must also exit zero, and
fails on a link into `evidence/` whose file does not exist:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-brief
```

A non-zero exit means the brief is not renderable yet (exit 2 means the file
is missing). Fix the brief, not the checker.
