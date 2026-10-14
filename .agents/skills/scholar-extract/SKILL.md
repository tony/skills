---
name: scholar-extract
description: >-
  Harvest terms and their definitions from a gathered corpus into
  terms.jsonl, each with the citation that supports it
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--out=<dir>]"
  source: "plugins/scholar/skills/extract/SKILL.md"
---

# this skill

Stage 2. Harvest the terms the corpus uses for its own things, each with a
citation that shows the term in use.

Read `references/citation.md` for what a citation must carry, including
why a quotation containing its own term is circular, and
`references/source-pins.md` for repository pins. Read
`references/stage-gates.md` for this stage's exit condition. The
analyzer is `references/term_metrics.py`; `<analyzer>` below is its absolute
path resolved from this skill's directory.

User arguments: $ARGUMENTS

Read `references/output-contract.md` before writing study files.

## What counts as a term

A term is a word the corpus uses for one of its own concepts. In code that is
the names it gives things: type and class names, module and package names,
recurring verbs in function names and commit subjects, the roles in its
configuration, the nouns in its error messages. In prose it is the author's
own vocabulary, taken from `quotations.jsonl`, the quotation set `annotate`
writes in the study directory.

A term is not a word that merely appears. `handler` is a term where the
project distinguishes handlers from services; it is noise where it is just
what someone called a function once.

## Procedure

### 1. Read the source list

Take `sources.jsonl` from `gather`. Harvest only from sources marked
`"read": true`.

### 2. Put the corpus on disk, read-only

Read each code source at its recorded `commit`, never at a moving branch.
`<pins>` is `references/scholar_pins.py`, resolved against this skill's directory to
an absolute path.

A checkout already on disk is read in place when this exits zero; `<study>` is
the study directory, which the dirty-tree check leaves out when it sits inside
the checkout:

```console
$ python3 <pins> local <corpus> \
    --study <study> \
    --expect <commit>
```

A refusal (uncommitted edits, or HEAD at another commit) is reported, not
harvested.

A remote source gets a throwaway checkout outside the study and outside the
current repository, fetched with plain git from the `source` URL, so any host
that serves git over HTTPS works. Take URL and COMMIT from `sources.jsonl`.
The command refuses a URL or commit it does not accept (mark that source
unharvested) and prints the checkout path on success; use that literal path
afterwards:

```console
$ python3 <pins> remote URL COMMIT
```

A refusal, including a host that will not serve a commit by SHA, means the
source is unreachable: mark it unharvested and say so. When harvesting and the
gate are done, delete each throwaway checkout:

```console
$ python3 <pins> release <checkout>
```

Prose sources need no checkout: harvest from `quotations.jsonl` in the study
directory, or stop and name `annotate` if it is missing.

### 3. Harvest

For code, the cheapest high-yield pass. `<corpus>` is the checkout path from
step 2. The pattern covers declaration modifiers (`public`, `abstract`,
`export default`, `async`, `sealed`, `data`) and the keywords `class`,
`struct`, `interface`, `enum`, `trait`, `type`, `object`, `def`, `fn`, `fun`
and `func`; a language that declares names another way needs its own pattern:

```console
$ rg \
    -o \
    --no-filename \
    -r '$1' \
    '^\s*(?:(?:export|default|public|private|protected|internal|static|final|abstract|sealed|open|data|async|pub(?:\([a-z]+\))?)\s+)*(?:class|struct|interface|enum|trait|type|def|fn|fun|func|object)\s+(\w+)' \
    <corpus> \
    | sort | uniq -c | sort -rn
```

The match anchors at the line start so a comment's "type of" does not count;
discard a stray `of` row.

Commit subjects need history, which the shallow checkout lacks; run this only
on a full local checkout:

```console
$ git -C <corpus> log --format=%s | rg -o '^\w+' | sort | uniq -c | sort -rn
```

Read the results; do not paste them into the table. Frequency proposes a
candidate, the corpus's own definition confirms it.

### 4. Write terms.jsonl

One row per sense, in the corpus's spelling. A word the corpus uses for two
concepts gets two rows with the same `term`; `contest` tests that pair for
polysemy.

```json
{"schema": 1, "term": "adapter", "definition": "wraps a third-party client behind the port interface", "parent": "", "kind": "role", "cites": [{"source": "https://github.com/OWNER/REPO", "url": "https://github.com/OWNER/REPO/blob/v2.40.0/src/ports.py#L12-L18", "locator": "src/ports.py:12-18", "quote": "every third-party client enters through a port"}]}
```

A prose cite has no `url`; it names its source by id instead:

```json
{"schema": 1, "term": "boundary", "definition": "the line a module's public surface stops at", "parent": "", "kind": "concept", "cites": [{"source": "style-guide-essay", "locator": "ch.3 §2", "quote": "the boundary is where the public surface stops"}]}
```

`source` is the `source` value of the cite's row in `sources.jsonl`: for a
pasted excerpt that is its `corpus/excerpt-<n>.txt` path. The fields are
defined in `references/citation.md`.

`parent` stays empty here. `distill` assigns it.

`kind` is one of `class`, `module`, `verb`, `role`, `message`, or `concept`
(prose); the term gate rejects any other value.

A class, struct, interface, or type-alias name is `kind: class`. `distill` alone
writes `kind: type` rows (exemption in `references/stage-gates.md`);
never emit `kind: type`.

`schema` is the row format's version. It costs one integer now and cannot be
added later without guessing what unversioned rows meant.

`definition` is drawn from the corpus, not composed. Where the corpus never
defines the term, record the definition its usage implies. Keep the definition
free of provenance notes ("implied by usage"); the analyzer scores definition
text. Record an implied definition as an open claim in `evidence/contested.md`
with the Claim, Objection, Evidence and Verdict (`open`) fields `contest`
uses. `Write` creates the file only when it is missing; otherwise add the entry with
`Edit` at its end.

## Rules

- Do not normalize spellings. `bump` and `update` staying separate is what
  lets `contest` find the synonymy; merging them here destroys the evidence.
- Distributional claims are `contest`'s to make, and they go in
  `evidence/metrics.md`, not on a term row.
- Every cite carries a verbatim `quote` and a `source`; the gate rejects a cite without either.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> terms extracted from
<n> sources`, `⚠ Gate failed: <n> findings`, or `⚠ Blocked: <reason>`. Sections:

1. `## Terms`: count by `kind`, and the ten most frequent with their
   definitions.
2. `## Rejected`: candidates that looked like terms and were not, with why.
3. `## Gate`: the output of the term check and the quote check in
   `references/stage-gates.md`, run once per source checkout from step 2
   (a prose-only study passes `--check-quotes` with no checkout).
   Report `Uncheckable` lines without failing. A failing check, or a
   `Misquoted` or `Vanished` line, is a failed gate: fix the row from the
   corpus text and rerun before reporting.

A halted run follows the halted-run shape in the output contract. Do not name
the checkout path:

```text
⚠ Blocked: the corpus checkout has uncommitted edits.

Commit them in the checkout or pass a scope that excludes them, then rerun scholar-extract.
```

Next-step options: run distill, harvest another source, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
