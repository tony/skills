---
name: ask
description: "Answer a question from a finished study, citing back into its evidence, and say plainly when the study does not cover it"
allowed-tools: ["Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "<question> [--study=<dir>]"
disable-model-invocation: true
---


# /scholar:ask

Consult a study instead of re-reading the corpus. Answers come from
`terms.jsonl` and the evidence documents, and they carry the citation the
study already earned.

User arguments: $ARGUMENTS

Without `--study`, the study is found as stage-gates.md describes under "The
study directory" (`../../references/stage-gates.md`).

Read `../../references/output-contract.md` before answering.

## Answer from the evidence, or name the gap

An agent asked a question about a corpus it has partly read will reason from
the parts it has to the parts it has not, and the result is indistinguishable
in tone from an answer it actually knows. This skill does not do that.

Where the study does not cover the question, say so, and say what would have
to be read to cover it. That answer is more useful than a plausible one,
because it can be acted on: `sources.jsonl` already records what was skipped
and why.

## Procedure

### 1. Locate the question in the ontology

Which terms does it touch, and which types do they sit under. A question that
touches no term in the table is a coverage question, not a lookup.

### 2. Answer from the rows

Every claim in the answer names the evidence file and the term row it came
from. An answer with no citations is either trivial or invented.

### 3. Trace on request

"Show me the evidence for X" is a question this skill answers: the term's
definition, every citation with its locator, any measurement that mentions it,
and any verdict `contest` recorded about it. That chain is what lets a reader
check the study rather than trust it.

### 4. Say what is missing

Distinguish three cases, because they mean different things:

- The study covers the question and the answer is here.
- The study read the relevant source and the corpus does not settle the
  question. That is a fact about the corpus.
- The study never read the relevant source. That is a fact about the study,
  and `sources.jsonl` says why it was skipped.

## Rules

- Never cite the corpus directly. If the answer needs a source the study did
  not read, that is case three; report it and stop.
- Quote the study's own words for a definition rather than paraphrasing; a
  paraphrase silently drops the distinction the term exists to carry.

## Output

Per `../../references/output-contract.md`. Hero: `✓ answered from <n> terms`,
`⚠ Not covered: <what would have to be read>` when the study exists but does
not settle the question, or `⚠ Blocked: <reason>` when no study is at the path.
A question the study answers in part takes the `✓` hero, with the rest under
`## Gaps`.
A blocked run is the halted-run shape; the unblock is the real study path, or
`/scholar:ontology` to build one:

```text
⚠ Blocked: no study at notes/ontology/sample-lib/, so there is no terms.jsonl to answer from.

Pass --study with the path of an existing study, or run /scholar:ontology on the corpus.
```

Sections, for the first two heroes:

1. `## Answer`: the answer, each claim citing its evidence file and row.
2. `## Evidence`: the chain: definitions, citations with locators, and any
   verdict recorded about the terms involved.
3. `## Gaps`: what the question needs and the study does not settle, and
   which of the three cases applies. Add no gap the question did not ask
   about.

The hero is exactly the line above, with nothing after the count.

Next-step options: widen the study to cover the gap, ask another question, stop
here.

Write it per `../../references/prose-rules.md`.
