---
name: revise
description: "Record a correction to a standing claim — what was believed, what it rested on, and why it failed — rather than editing it away"
allowed-tools: ["Bash", "Read", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "<term-or-claim> [--study=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:revise

Something the study asserted turned out to be wrong. This records that, rather
than quietly making it true.

User arguments: $ARGUMENTS

## Why a correction is kept

A retracted claim is worth more written down than deleted. Deleting it does
not delete it from anyone's memory. A figure that circulated and turned out to
measure something else keeps being repeated by everyone who read it before the
fix, and they have no way to learn otherwise unless the study says so.

The correction also carries information the replacement does not: knowing that
a plausible reading of the evidence was wrong tells the next reader which
plausible readings to distrust.

## Procedure

### 1. Establish what is being overturned

Usually from `/scholar:verify` (a citation that no longer says what it was
quoted as saying) or from `/scholar:contest` (a later round that killed an
earlier verdict). Take the claim as it currently stands, verbatim.

### 2. Append to evidence/corrections.md

```markdown
## <the term or claim>

**Was:** the claim as it stood, quoted exactly.

**Rested on:** the citation or measurement that supported it.

**Failed because:** what overturned it, cited or measured.

**Now:** the replacement claim, or a statement that the question is open.
```

Append. Never rewrite an existing correction — a correction that was itself
wrong gets its own entry beneath.

### 3. Update the study

Change the affected row in `terms.jsonl` and the affected evidence document,
then link the correction from the brief's section so a reader of the brief
meets it. A brief edit can break the brief gate, so run it and report the
result in `## Touched`:

```console
$ <analyzer> notes/ontology/<subject>/ --check-brief
```

`<analyzer>` is `../../references/term-metrics.py`. Fix the brief until it
exits zero.

## Rules

- A correction states what overturned the claim, with the same evidence tier
  the claim itself required. "This turned out to be wrong" is not a
  correction.
- Where the replacement is "we do not know", say that. A confident replacement
  invented to fill the hole is worse.

## Output

Per `../../references/output-contract.md`. Hero: `✓ corrected <claim>` or `⚠
Blocked: <reason>`. Sections:

1. `## Correction` — the four fields, as written to the file.
2. `## Touched` — the rows and evidence documents updated.
3. `## Downstream` — anything else in the study that rested on the same
   evidence and may now be unsupported.

Next-step options: verify the downstream claims, re-run contest, stop here.

Write it per `../../references/prose-rules.md`.
