---
name: gather
description: "Resolve and pin a corpus, inventory it, and record what was read and what was deliberately skipped, into sources.jsonl"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
argument-hint: "<target>... [--kind=code|prose] [--out=<dir>]"
disable-model-invocation: true
---


# /scholar:gather

Stage 1. Turn a loose target (a repository, a set of them, a book) into a
pinned, inventoried source list a later stage can cite against.

Read `../../references/source-pins.md` for how to pin,
`../../references/citation.md` for citation fields, and
`../../references/stage-gates.md` for this stage's exit condition.

User arguments: $ARGUMENTS

Read `../../references/output-contract.md` before writing study files.

## The invariant

Never write into the corpus being read: no `git checkout`, no `git clean`, no
edit inside a target. Studying a project must not dirty its checkout. Output
lands under `--out`, defaulting to `notes/ontology/<subject>/` in the current
repository, even when that repository is the corpus: the dirty-tree checks in
`gather` and `extract` leave the study directory out, so the study does not
block the next stage. The corpus is recorded by URL and ref; `extract` fetches a pinned checkout
when it needs one. A checkout with no remote is recorded by its directory name
(step 1). A pasted excerpt is the exception: it has no
URL, so it is stored under `--out`.

## Procedure

### 1. Resolve each target to a ref

Resolve repository targets using `source-pins.md`.

For a local checkout, run these checks first, each against the corpus with
`git -C <corpus>`, since the corpus is not necessarily the working directory.
Each must hold or the pin cannot be reproduced elsewhere:

```console
$ git -C <corpus> status \
    --porcelain
```

Output means uncommitted edits: the working tree differs from the commit, so
stop and ask the user to commit or pass a scope that excludes them. When the
study's `--out` directory lives inside the corpus checkout, add
`-- . ':(exclude)<out relative to the corpus>'` so the study's own files do
not count.

```console
$ git -C <corpus> branch \
    --remotes \
    --contains HEAD
```

No output means the commit is not pushed, so a permalink to it can 404. Pin a
pushed ref instead, or record the source without a URL (below).

```console
$ git -C <corpus> rev-parse --short HEAD
```

Record the resolved commit as `commit` so `verify` can detect a moved tag.

For a local checkout, the ref is the tag only when
`git -C <corpus> describe --tags --exact-match HEAD` prints it; otherwise it
is the 7-character HEAD, with no tag. Record `commit` from that same ref:
`git -C <corpus> rev-parse 'REF^{commit}'`. Quotes are read at HEAD, so a tag
behind HEAD is never the ref. For a remote on
another host, `git ls-remote URL REF 'REF^{}'` prints it; the peeled line
(`REF^{}`) is the commit of an annotated tag, else use the plain line.

A checkout with no remote has no URL form. Publish it first, or record
`source` as the repository's directory name, leave `url` out of every cite, and
cite `path@commit` in `locator`; `verify` checks those with `git show` inside
that repository.

For prose, the ref is the edition: publisher, year, and printing. It has no
`commit`; leave it empty. A pasted prose excerpt is saved verbatim to
`<out>/corpus/excerpt-<n>.txt` (n counts from 1), and that path relative to `<out>`
is the row's `source`. Name no title the user did not give.

### 2. Inventory without reading everything

Establish the shape of the corpus cheaply. For code, the module or package
list and the size of each. For prose, the table of contents. For several
repositories, the list and what each one is for.

### 3. Decide scope with the user

Present the inventory via `AskUserQuestion` and settle what will be read. Most
studies should not read everything. Where no question tool exists, print the
inventory and a proposed scope, then stop without writing `sources.jsonl`.
A scope the user named in the request is already settled; do not ask again.

### 4. Write sources.jsonl

One row per source, including every source deliberately not read:

```json
{"source": "https://github.com/OWNER/REPO", "ref": "v2.40.0", "commit": "<40-character SHA>", "scope": "src/parser/", "locator_kind": "line-range", "read": true, "why": ""}
{"source": "https://github.com/OWNER/REPO", "ref": "v2.40.0", "commit": "<40-character SHA>", "scope": "test/", "locator_kind": "line-range", "read": false, "why": "tests name fixtures, not domain concepts"}
{"source": "Example Press, Style Guide", "ref": "2024, first printing", "commit": "", "scope": "chapter 2", "locator_kind": "search-string", "read": true, "why": ""}
```

`locator_kind` is how citations into the source are located: `line-range`,
`section`, `page`, or `search-string`, defined in
`../../references/citation.md`. `annotate`, `extract`, and `verify` all use
these four values.

`contest`'s completeness pass reads exactly this file.

## Rules

- Report results, not reasons: no "has no title because" or "uses search-string
  because" in the output.
- Never justify a step in the output ("the edition comes from the request",
  "the ref is the edition you gave", "saved word for word", "the commit field
  is empty, and citations are located by search string"): state what was
  recorded. For prose the whole line is "Commit: none"; the ref is only
  the edition as given ("2024, first printing"), with no reason after it. List
  `sources.jsonl` under `## Pinned` as its path under `--out`.
- A commit not on any remote is recorded as "commit not on a remote; recorded
  without URL".
- "Out of scope" is not a reason in `why`. Say what the source contains and why
  that does not bear on the vocabulary.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <subject>: <n> sources
pinned, <n> skipped` or `⚠ Blocked: <reason>`. Sections:

1. `## Pinned`: the `sources.jsonl` written, as a path under `--out`, then
   each source read, its ref, and how the ref was resolved.
2. `## Skipped`: each source not read, and why.
3. `## Shape`: the inventory that informed the scope decision, stated as
   what is there ("one excerpt, two sentences"), never as what is missing.

Next-step options: run extract, widen scope, stop here.

Write it per `../../references/prose-rules.md`.
