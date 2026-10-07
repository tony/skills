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
`references/stage-gates.md` for this stage's exit condition. The
analyzer is `references/term_metrics.py`; `<analyzer>` below is its absolute
path resolved from this skill's directory.

User arguments: $ARGUMENTS

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

Read each code source at its recorded `commit`, never at a moving branch. A
checkout already on disk is read in place once `git rev-parse HEAD` matches
the row's `commit` and `git status --porcelain` prints nothing; a mismatch or a
dirty tree is reported, not harvested. A remote source
gets a throwaway checkout outside the study and outside the current
repository. Take OWNER, REPO and COMMIT from `sources.jsonl`; run the command
only when each is made of letters, digits, `.`, `_`, and `-`, and otherwise
mark the source unharvested. This command prints its path; use that literal path afterwards:

```console
$ dir=$(mktemp -d "${TMPDIR:-/tmp}/scholar-corpus.XXXXXX") \
    && git -C "$dir" init --quiet \
    && git -C "$dir" fetch --quiet --depth 1 https://github.com/OWNER/REPO COMMIT \
    && git -C "$dir" checkout --quiet FETCH_HEAD \
    && echo "$dir"
```

A failed fetch means the source is unreachable; mark it unharvested and say
so. Prose sources need no checkout: harvest from `quotations.jsonl` in the study
directory, or stop and name `annotate` if it is missing.

### 3. Harvest

For code, the cheapest high-yield passes, all portable. `<corpus>` is the
checkout path from step 2:

```console
$ rg \
    -o \
    --no-filename \
    -r '$1' \
    '\b(?:class|struct|interface|type)\s+(\w+)' \
    <corpus> \
    | sort | uniq -c | sort -rn
```

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
{"schema": 1, "term": "adapter", "definition": "wraps a third-party client behind the port interface", "parent": "", "kind": "role", "cites": [{"url": "https://github.com/OWNER/REPO/blob/v2.40.0/src/ports.py#L12-L18", "locator": "src/ports.py:12-18", "quote": "every third-party client enters through a port"}]}
```

`parent` stays empty here. `distill` assigns it.

`kind` is one of `type`, `module`, `verb`, `role`, `message`, or `concept`
(prose).

`schema` is the row format's version. It costs one integer now and cannot be
added later without guessing what unversioned rows meant.

`definition` is drawn from the corpus, not composed. Where the corpus never
defines the term, record the definition its usage implies and say so in the
citation's quote by choosing a passage that shows the usage.

## Rules

- Do not normalize spellings. `bump` and `update` staying separate is what
  lets `contest` find the synonymy; merging them here destroys the evidence.
- Distributional claims are `contest`'s to make, and they go in
  `evidence/metrics.md`, not on a term row.
- Every cite carries a verbatim `quote`; the gate rejects a cite without one.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> terms extracted from
<n> sources` or `⚠ Blocked: <reason>`. Sections:

1. `## Terms` — count by `kind`, and the ten most frequent with their
   definitions.
2. `## Rejected` — candidates that looked like terms and were not, with why.
3. `## Gate` — the output of the term check, which exits zero only when every
   row has a definition and a quoted citation:

   ```console
   $ python3 <analyzer> notes/ontology/<subject>/ --check-terms
   ```

A halted run follows the halted-run shape in the output contract. Do not name
the checkout path.

Next-step options: run distill, harvest another source, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
