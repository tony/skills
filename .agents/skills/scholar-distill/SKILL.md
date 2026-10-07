---
name: scholar-distill
description: >-
  Build the three ontology layers from a term table: types, members with
  discriminators, and the controlled vocabulary
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--out=<dir>]"
  source: "plugins/scholar/skills/distill/SKILL.md"
---

# this skill

Stage 3. Turn a flat term table into an ontology. Three layers, in order. Any
one of them alone is not an ontology.

Read `references/evidence-tiers.md` for what each claim must carry and
`references/stage-gates.md` for this stage's exit condition. The analyzer
is `references/term_metrics.py`; `<analyzer>` below is its absolute path
resolved from this skill's directory.

User arguments: $ARGUMENTS

## Layer 1: types

The is-a hierarchy. What kinds of thing the corpus contains.

Write it to `evidence/hierarchy.md`, one citation per is-a claim. Each type is
also a row in `terms.jsonl` with `kind: type`, its discriminator as
`definition`, and `parent` set to another type or the literal string `root`.
Write each type's name onto its members' rows as `parent`. A type row you create
carries no `cites`; the `--check-terms` gate exempts a `kind: type` row that
has a `parent`, and the citations live in `hierarchy.md`. A type the corpus
already names (a `class`) keeps the row `extract` wrote: change its `kind` from
`class` to `type` in place, `cites` included.

Types come from the corpus's own distinctions. If a project separates ports
from adapters everywhere, those are types. If the analyst finds it tidy to
group four things, that is not a type.

## Layer 2: members with discriminators

For each type, the test that decides membership. Write it into
`evidence/hierarchy.md` beside the type.

This is what separates an ontology from a labelled list:

- A discriminator: *a plugin is an agent domain iff its name denotes a doer
  rather than the thing acted on.*
- Not a discriminator: *these four feel similar.*

A type whose discriminator you cannot write is not a type yet. Either find the
test, or dissolve the type and return its members to their parent.

## Layer 3: the controlled vocabulary

Write `evidence/vocabulary.md`: per act or relation the corpus performs, the
preferred term, its deprecated variants, and the disjointness constraints
between siblings.

Three properties, all checkable by `contest`:

- One term, one referent. No polysemy. A term standing for two concepts is
  the failure that makes a vocabulary unusable.
- One referent, one term. No synonymy. Four names for one act is four
  chances to miss the fourth.
- Siblings disjoint. No two sibling terms both correctly describe one
  instance.

The preferred term is the one the corpus already uses most, not the one that
reads best. A vocabulary that renames what the corpus says has stopped
describing it.

## The orphan gate

Run the analyzer and read its `orphans` section:

```console
$ python3 <analyzer> notes/ontology/<subject>/
```

Then confirm the table still passes the term gate:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-terms
```

A term with no `parent` is an orphan, as is one whose parent is neither
another term nor `root`. Report a member (non-type row) whose parent is
`root` as an orphan too: only types sit under `root`. The analyzer's `hierarchy cycles` section lists any
parent chain that returns to itself, such as `a -> b -> a` or a term that is
its own parent; fix each by re-reading the corpus's own is-a claim. An orphan
is a finding: either the corpus has a
concept the hierarchy has not named, or the term does not belong in the table.
Never invent a type to house an orphan, and never split a type to tidy its
fan-out. Both produce a hierarchy that describes the analyst's sense of order
rather than the corpus.

## Rules

- A term keeps the spelling `extract` recorded. The vocabulary names a
  preferred term; it does not rewrite the rows.
- Deprecated variants stay in the table. They are what a reader of the corpus
  will actually encounter.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> types, <n> terms, <n>
preferred terms`, `⚠ Gate failed: <n> orphans, <n> cycles`, or `⚠ Blocked:
<reason>`. A failed gate prints the hero, then each orphan or cycle on its own
line, then the fix; no other sections. Sections:

1. `## Types`: the hierarchy, each type with its discriminator.
2. `## Vocabulary`: preferred terms with their deprecated variants.
3. `## Unresolved`: terms that resisted placement, and what that suggests
   about the corpus rather than about the table.

Next-step options: run contest, revisit a type, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
