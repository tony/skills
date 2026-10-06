---
name: annotate
description: "Take reading notes on a prose corpus — quotations with stable locators and margin notes, as a term source for extract"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write"]
argument-hint: "<source> [--locator=chapter|section|page|line] [--out=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:annotate

The prose path. Without it, a written corpus enters the pipeline as
unstructured text and its citations degrade to "somewhere in chapter 3".

Read `../../references/citation.md` for the locator rules this stage
implements: take the most stable locator the source supports.

User arguments: $ARGUMENTS

## Procedure

### 1. Confirm the edition

Read the source's row in `sources.jsonl`. If the locator scheme is `page` and
the edition is unrecorded, stop and record the edition first.

### 2. Extract quotations

One quotation per concept the author names, long enough to stand on its own
when read out of context. A quotation that only makes sense beside the
sentence before it is too short.

### 3. Attach margin notes

The note says what the quotation is evidence *for* — which is the analyst's
judgement and must stay visibly separate from the author's words. Never blend
the two into a paraphrase; `extract` needs to know which is which.

### 4. Write the quotation set

```
{"source": "<source id from sources.jsonl>", "locator": "ch.3 §2", "quote": "...", "note": "the author's own term for the boundary"}
```

## Rules

- The quotation is verbatim. An ellipsis marks every omission.
- A term the author uses without defining is still a term. Quote a passage
  showing the usage rather than skipping it.
- Where the author defines a term explicitly, quote the definition and mark it,
  so `extract` can use it directly rather than inferring one.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <n> quotations from
<source>`. Sections:

1. `## Quotations` — count by locator kind, and the concepts they name.
2. `## Locator` — which scheme this source uses and why, including any
   fallback to a search string.
3. `## Undefined` — terms the author uses without defining, which `extract`
   will have to infer from usage.

Next-step options: run extract, annotate another source, stop here.
