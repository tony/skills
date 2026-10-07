# scholar

Distil a checkable ontology from a codebase, a repository set, or a written
corpus. The product is a type hierarchy plus a controlled vocabulary, a short
human-readable brief, and an evidence layer that lets a third party check
every claim.

An agent that has read a corpus usually returns a summary. A summary cannot be
checked, does not compose, and rots without saying so. The test this plugin is
built against: can a reader who was not present disagree with a specific
claim, find what it rests on, and re-derive it?

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install scholar@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add scholar@skills
```

Claude Code uses a leading slash (`/scholar:…`). Codex omits it (`scholar:…`).

## Skills

Each skill is invoked by name. Codex drops the leading slash (`scholar:ontology`).

Distil an ontology, controlled vocabulary, or glossary of what a codebase, a repository set, or a written corpus calls things:

```console
$ /scholar:ontology [<target>...]
```

Resolve and pin a corpus, inventory it, and record what was read and what was deliberately skipped:

```console
$ /scholar:gather <target>...
```

Harvest terms and their definitions into a term table, each with the citation that supports it:

```console
$ /scholar:extract
```

Build the three layers: types, members with discriminators, and the controlled vocabulary:

```console
$ /scholar:distill
```

Adversarially judge the ontology one candidate at a time, recording the kills:

```console
$ /scholar:contest
```

Write the brief and the evidence documents, then enforce the brief's citation prohibition:

```console
$ /scholar:render
```

Reading notes on prose: quotations with stable locators, as a term source for extract:

```console
$ /scholar:annotate <source>
```

Answer from a finished study, citing its evidence, and name the gap when there is one:

```console
$ /scholar:ask <question>
```

Set two term tables against each other: shared concepts, clashing terms, and coverage:

```console
$ /scholar:compare <dir> <dir>
```

Record a correction: what was believed, what it rested on, and why it failed:

```console
$ /scholar:revise <claim>
```

Re-check a study against the corpus it cites: moved refs, vanished files, misquotes, changed numbers:

```console
$ /scholar:verify [<dir>]
```

`ontology` is the only skill a model routes to on its own. The rest are
invoked by name, so the pipeline can be resumed at any stage.

## Artifacts

A study is a directory, not a document:

```
notes/ontology/<subject>/
├── brief.md              the only file meant to be read start to finish
├── terms.jsonl           interchange: {schema, term, definition, parent, kind, cites}
├── sources.jsonl         {source, ref, commit, scope, locator_kind, read, why}
├── quotations.jsonl      prose only: {source, locator_kind, locator, quote, note}
└── evidence/
    ├── hierarchy.md      the type hierarchy, one citation per is-a claim
    ├── vocabulary.md     preferred and deprecated terms, disjointness constraints
    ├── metrics.md        distributional claims, each with its command and output
    ├── contested.md      claim, objection, verdict, including the kills
    └── corrections.md    retractions: what was believed, and why it failed
```

`terms.jsonl` is the seam everything composes on. Stages do not call each
other; they read and write these files. A term table written by hand, or by a
different tool entirely, is a valid input to `contest` and `render`.

`brief.md` may not contain a citation, a permalink, or a bare number. Where it
wants one it links into `evidence/`. `render` enforces this with
`scripts/term_metrics.py --check-brief`, so the top layer stays readable by
construction rather than by discipline.

## Composition

Every one of these is optional. `scholar` works standalone.

`weave`: `contest --panel` prints a contested claim and a `/weave:ask`
command for you to run; paste the verdicts back and `contest` records them
beside the serial one.

## Prerequisites

- git, to resolve and pin a corpus to a ref.
- gh, to resolve a tag to its commit and to check it again in `verify`.
  `verify` checks GitHub sources only; a corpus on another host is Uncheckable
  there unless a local clone is on disk, which `verify` checks with plain git.
  `extract` fetches a remote corpus with plain git over HTTPS from the recorded
  source URL, so any host that serves git works.
- rg, to inventory a corpus without reading all of it.
- Python 3.9+, to run `scripts/term_metrics.py`. It uses the standard library
  only, so it runs inside any corpus checkout with no package manager present.

A corpus with no git remote cannot be cited by permalink. Publish it first, or
cite `path@commit`, which `verify` checks with `git show`.

A small repository does not need every stage: run `gather` and `extract`, then
`render`, and add `distill` and `contest` once the term table passes about 20
terms and has siblings to tell apart.
