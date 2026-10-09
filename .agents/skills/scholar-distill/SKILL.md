---
name: scholar-distill
description: >-
  Build source-supported types, memberships, and controlled vocabulary from
  a term table
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

Read `references/output-contract.md` before writing study files.

## Layer 1: types

The is-a hierarchy. What kinds of thing the corpus contains.

Write it to `evidence/hierarchy.md`, citing each type declaration and is-a
claim. Each type is also a row in `terms.jsonl` with `kind: type`, its
corpus-supported `definition`, and `parent` set to another type or the literal
string `root`.
Write each type's name onto its members' rows as `parent`. A type row you create
carries no `cites`; the `--check-terms` gate exempts a `kind: type` row that
has a `parent`, and the citations live in `hierarchy.md`. A type the corpus
already names (a `class`) keeps the row `extract` wrote: change its `kind` from
`class` to `type` in place, `cites` included.

Each non-root parent needs a source-supported is-a or member relation.
Sharing a file, directory, or prefix does not establish that relation.
`root` is the special anchor for top-level types, not an invented type.

## Layer 2: supported memberships

Record the corpus's basis for membership in `evidence/hierarchy.md`. A code
declaration supports a named type even when the corpus gives no behavioral
membership test. Keep its documented role separate from that declaration.

Use a necessary-and-sufficient discriminator only when the source establishes
both directions. A docstring describing a type's role does not establish that
everything with that role belongs to the type, or that its members have no
other roles. Keep the extracted definition and citations; do not strengthen
a role description into such a test.

An analyst-proposed type without a supported membership relation remains
unsupported. Record the gap rather than inventing a type or parent.

## Layer 3: the controlled vocabulary

Write `evidence/vocabulary.md`: the corpus's terms, their senses, preferred
spellings, observed aliases, and any source-declared deprecations.

Preserve supported synonymy, multiple senses, and overlap. Cite each asserted
equivalence or disjointness constraint; sibling placement does not imply
disjointness. When the source leaves a relationship unknown, record that
limit without asserting either overlap or exclusion. Lexical similarity
proposes a question for `contest`, not a semantic relation.

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
may be a valid term whose parent the corpus does not establish. Retain it
and report the failed gate. Do not drop it or promote it without source
support to clear a finding. Never invent a type to house an orphan or split
a type to tidy its fan-out.

## Rules

- A term keeps the spelling `extract` recorded. The vocabulary names a
  preferred term; it does not rewrite the rows.
- Deprecated variants stay in the table. They are what a reader of the corpus
  will actually encounter.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> types, <n> terms, <n>
preferred terms`, `⚠ Gate failed: <n> orphans, <n> cycles`, or `⚠ Blocked:
<reason>`. A failed gate prints the hero, then each orphan or cycle on its own
line, then one sentence naming the terms whose corpus evidence must be
re-read before assigning parents, with no
quoted corpus text, not even in parentheses; no other sections. Reply as plain text outside any code
fence, with plain bullets, no bold (never `- **Label:** ...`), and no local
paths. Never narrate files you did not write ("I changed nothing"), and never
quote the skill's own instructions:

```text
⚠ Gate failed: 1 orphan, 1 cycle

- Orphan: checkpoint has no parent.
- Cycle: phase -> stage -> phase.

Re-read the corpus evidence for checkpoint, stage, and phase before assigning parents, then rerun the gate.
```

Sections:

1. `## Types`: the hierarchy and each type's supported membership basis.
2. `## Vocabulary`: preferred terms with their deprecated variants.
3. `## Unresolved`: terms that resisted placement, and what that suggests
   about the corpus rather than about the table.

Next-step options: run contest, revisit a type, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
