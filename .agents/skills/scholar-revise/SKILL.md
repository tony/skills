---
name: scholar-revise
description: >-
  Record a correction to a standing claim: what was believed, what it rested
  on, and why it failed, rather than editing it away
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "<term-or-claim> [--study=<dir>]"
  source: "plugins/scholar/skills/revise/SKILL.md"
---

# this skill

Something the study asserted turned out to be wrong. This records that, rather
than quietly making it true.

User arguments: $ARGUMENTS

`<analyzer>` is `references/term_metrics.py`, resolved against this skill's
directory to an absolute path.

Without `--study`, the study is found as "The study directory" describes in
`references/stage-gates.md`.

Read `references/output-contract.md` before writing study files.

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

Usually from the `scholar-verify` skill (a citation that no longer says what it was
quoted as saying) or from the `scholar-contest` skill (a later round that killed an
earlier verdict). Take the claim as it currently stands, verbatim.

Read the source the claim rested on at its recorded pin, and the evidence that
overturns it. A correction written from the study's stored quotations alone
repeats whatever they got wrong. When the source cannot be read, stop with
`⚠ Blocked` naming it.

### 2. Record the correction first

Append the entry to `evidence/corrections.md` before any edit to
`terms.jsonl`, an evidence document, or the brief. An interrupted run then
leaves the retraction on disk rather than a claim changed with no record.

```markdown
## <the term or claim>

Was: the claim as it stood, quoted exactly.

Rested on: the citation or measurement that supported it.

Failed because: what overturned it, cited or measured.

Now: the replacement claim, or a statement that the question is open.
```

Append with `Edit` at the end of the file; never `Write` it back whole. Never
rewrite an existing correction: a correction that was itself wrong gets its
own entry beneath. Then read it back; this exits zero only when every entry
carries all four fields and the last one is the claim just recorded, so a
correction that did not land stops the run before step 3:

```console
$ python3 <analyzer> notes/ontology/<subject>/ \
    --check-corrections "<the term or claim>"
```

### 3. Update the study

Only after step 2 is on disk, change the affected row in `terms.jsonl` and the affected evidence document,
then link the correction from the brief's section so a reader of the brief
meets it. A brief edit can break the brief gate, so run it and report the
result in `## Touched`:

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-brief
```

Fix the brief until it exits zero.

## Rules

- A correction states what overturned the claim, with the same evidence tier
  the claim itself required. "This turned out to be wrong" is not a
  correction.
- Where the replacement is "we do not know", say that. A confident replacement
  invented to fill the hole is worse.

## Output

Per `references/output-contract.md`. Hero: `✓ corrected <claim>` or `⚠
Blocked: <reason>`. Sections:

1. `## Correction`: the four fields as plain `Was: ...` lines, never bold.
2. `## Touched`: the rows and evidence documents updated, with no sentence
   about an entry or file left as it was.
3. `## Downstream`: anything else in the study that rested on the same
   evidence and may now be unsupported.

A halted run (no study, no standing claim to correct, or an unreadable source)
is the halted-run shape:

```text
⚠ Blocked: no study at notes/ontology/sample-lib/ to correct.

Pass the study path, or run scholar-ontology to build one.
```

Next-step options: verify the downstream claims, re-run contest, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
