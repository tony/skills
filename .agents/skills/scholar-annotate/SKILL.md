---
name: scholar-annotate
description: >-
  Take reading notes on a prose corpus: quotations with stable locators and
  margin notes, as a term source for extract
disable-model-invocation: true
allowed-tools: ["Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "<source> [--locator=line-range|section|page|search-string] [--out=<dir>]"
  source: "plugins/scholar/skills/annotate/SKILL.md"
---

# this skill

The prose path. Without it, a written corpus enters the pipeline as
unstructured text and its citations degrade to "somewhere in chapter 3".

Read `references/citation.md` for the locator rules this stage
implements: take the most stable locator the source supports.

User arguments: $ARGUMENTS

## Procedure

### 1. Confirm the edition

Read the source's row in `sources.jsonl`. `--locator` overrides the row's
`locator_kind`; the four kinds are defined in `references/citation.md`.
If the kind is `page` and the edition is unrecorded, or the source has no row,
stop with `⚠ Blocked` (see Output). `gather` writes `sources.jsonl` and
records the edition; the user may also add the row by hand.

### 2. Extract quotations

One quotation per concept the author names, long enough to stand on its own
when read out of context. A quotation that only makes sense beside the
sentence before it is too short.

### 3. Attach margin notes

The note says what the quotation is evidence *for*, which is the analyst's
judgement and must stay visibly separate from the author's words. Never blend
the two into a paraphrase; `extract` needs to know which is which.

### 4. Write the quotation set

Append one row per quotation to `quotations.jsonl` in the study directory
(`--out`, default `notes/ontology/<subject>/`). `extract` reads this file for
prose sources. When the file exists, Read it first and add the new rows with
`Edit` at its end; `Write` creates the file only when it is absent, never
replaces it, because an earlier source's rows live there.

```json
{"source": "<source id from sources.jsonl>", "locator_kind": "section", "locator": "ch.3 §2", "quote": "...", "note": "the author's own term for the boundary"}
```

When the kind is `search-string`, `locator` is the unique text that finds the
passage.

## Rules

- The quotation is verbatim. An ellipsis marks every omission.
- A term the author uses without defining is still a term. Quote a passage
  showing the usage rather than skipping it.
- Where the author defines a term explicitly, quote the definition and mark it,
  so `extract` can use it directly rather than inferring one.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> quotations from
<source>` or `⚠ Blocked: <reason>`. A blocked run prints the hero, one
sentence on the unblock, and nothing else: no text before the hero, no
sections, no restating the reason. Reply as plain text outside any code fence.

```text
⚠ Blocked: no sources.jsonl row for style-guide-essay, so its edition is unrecorded.

Run scholar-gather on the source, or add its row by hand, then run annotate again.
```

Sections:

1. `## Quotations`: the `quotations.jsonl` path under the study directory, the count by `locator_kind`, and the concepts they name.
2. `## Locator`: which `locator_kind` this source uses, including any
   fallback to `search-string`. Give no reasons.
3. `## Undefined`: terms the author uses without defining, which `extract`
   will have to infer from usage.

Next-step options: run extract, annotate another source, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
