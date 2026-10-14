---
name: compare
description: "Set two term tables against each other: same concept different term, same term different concept, and what each covers that the other lacks"
allowed-tools: ["Bash", "Read", "Glob", "Write", "AskUserQuestion"]
argument-hint: "<study-dir> <study-dir> [--out=<file>]"
disable-model-invocation: true
---


# /scholar:compare

Two studies, one question: where do these vocabularies agree, where do they
collide, and what does each one know that the other does not.

User arguments: $ARGUMENTS

## Two shapes of comparison

**Across projects.** What does tokio call the thing asyncio calls a task. Two
communities solving one problem rarely name it the same way, and the mapping
is most of what it costs to move between them.

**Across time.** One project's vocabulary at v1 against the same project at
v4. Drift that nobody announced is the drift that breaks readers of the old
documentation.

## Procedure

### 1. Load both tables

Take `terms.jsonl` from each study directory. Run the hierarchy gate in
`../../references/stage-gates.md` on each; a table that fails has empty or
dangling `parent` fields, so stop with the contract's failed-gate shape.
`<analyzer>` is `../../scripts/term_metrics.py`, resolved against this skill's
directory to an absolute path.

### 2. Report three sections

Mappings: definitions that say the same thing while the terms differ. These
are the translation table.

Collisions: identical terms whose definitions describe different things.
These are the traps: the reader who knows one project will be confidently
wrong about the other.

Coverage: what each table has that the other has no counterpart for. A
concept present in one and absent in the other is either a genuine difference
in what the projects do, or a gap in one of the studies. Say which only when
`sources.jsonl` shows what each study read; otherwise it is unknown, and the
reply names the source whose reading would settle it.

### 3. Judge by reading

Compare definitions side by side. The term analyzer scores
one table at a time, so no cross-table similarity exists; do not report one.
The hero counts are counts of findings, not scores.

## Rules

- Do not merge the tables. A comparison is a third document; the two studies
  stay as they are.
- Two terms with alike definitions are a candidate mapping, not a mapping.
  Say what the definitions have in common and where they part.
- State only what the two tables say. Do not add behavior, architecture, or
  where a feature "would live" that no definition or citation states; what
  the definitions leave out is unknown.
- Where the two studies read corpora at different depths, say so. A coverage
  gap between an exhaustive study and a shallow one is a fact about the
  studies, not about the projects.

## Output

Per `../../references/output-contract.md`, which you read before writing
`--out`. Hero: `✓ <n> mappings, <n>
collisions, <n> uncovered` or `⚠ Blocked: <reason>`. Sections:

1. `## Mappings`: same concept, different term, with both definitions.
2. `## Collisions`: same term, different concept, and what a reader moving
   between the two would get wrong.
3. `## Coverage`: what each side has that the other lacks, and whether that
   is a difference or a gap.

A halted run (a study with no `terms.jsonl`, or fewer than two studies) is the
halted-run shape, naming each missing study directory and the unblock
(`/scholar:ontology` to build it):

```text
⚠ Blocked: neither notes/ontology/sample-lib/ nor notes/ontology/other-lib/ exists.

Run /scholar:ontology on each corpus, then compare again.
```

With `--out=<file>`, also write the three sections to that file; without it,
write nothing.

Next-step options: study the uncovered area, stop here.

Write it per `../../references/prose-rules.md`.
