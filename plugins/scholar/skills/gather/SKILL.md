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

For a local checkout, resolve it with the pin script. `<pins>` is
`../../scripts/scholar_pins.py`, resolved against this skill's directory to an
absolute path, and `<out>` is the study directory:

```console
$ python3 <pins> local <corpus> \
    --study <out>
```

It exits non-zero with a one-line reason when the checkout has uncommitted
edits (files under `<out>` do not count), and otherwise prints one JSON line:
`commit` (the full 40 digits to record as `commit`), `ref` (the tag when one
points exactly at HEAD, else the 7-character HEAD), `tag`, and `pushed`.
Quotes are read at HEAD, so a tag behind HEAD is never the ref. A refusal
means: stop and ask the user to commit or pass a scope that excludes the
edits. `"pushed": false` means a permalink to the commit can 404: pin a pushed
ref instead, or record the source without a URL (below).

For a remote on another host, `git ls-remote URL REF 'REF^{}'` prints it; the
peeled line (`REF^{}`) is the commit of an annotated tag, else use the plain
line.

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

### 4. Write sources.jsonl and check it

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

Then read it back with the gate in `../../references/stage-gates.md`
(`--check-sources`) and fix every line it prints before reporting. `contest`'s
completeness pass reads exactly this file.

## Rules

- List `sources.jsonl` under `## Pinned` as its path under `--out`. For prose
  the commit line is "Commit: none"; the ref is only the edition as given
  ("2024, first printing").
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
