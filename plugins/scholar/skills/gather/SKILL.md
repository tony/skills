---
name: gather
description: "Resolve and pin a corpus, inventory it, and record what was read and what was deliberately skipped, into sources.jsonl"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
argument-hint: "<target>... [--kind=code|prose] [--out=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:gather

Stage 1. Turn a loose target (a repository, a set of them, a book) into a
pinned, inventoried source list a later stage can cite against.

Read `../../references/citation.md` for how to pin, and
`../../references/stage-gates.md` for this stage's exit condition.

User arguments: $ARGUMENTS

## The invariant

Never write into the corpus being read: no `git checkout`, no `git clean`, no
edit inside a target. Studying a project must not dirty its checkout. Output
lands under `--out`, defaulting to `notes/ontology/<subject>/` in the current
repository, even when that repository is the corpus: the dirty-tree checks in
`gather` and `extract` leave the study directory out, so the study does not
block the next stage. The corpus is recorded by URL and ref, not by local path; `extract` fetches a
pinned checkout when it needs one. A pasted excerpt is the exception: it has no
URL, so it is stored under `--out`.

## Procedure

### 1. Resolve each target to a ref

For a git repository, prefer a release tag; fall back to a 7-character commit
reachable from trunk. Never a branch name: it moves, and every citation built
on it rots silently.

Newest tag of a repository you have not cloned:

```console
$ gh release list \
    --repo OWNER/REPO \
    --limit 1 \
    --exclude-drafts \
    --exclude-pre-releases \
    --json tagName \
    --jq '.[0].tagName'
```

A repository can have thousands of tags and no releases, in which case that
prints nothing. Fall back to the tags:

```console
$ git ls-remote \
    --tags \
    --refs \
    --sort=-v:refname \
    https://github.com/OWNER/REPO
```

For a local checkout, run these checks first. Each must hold or the pin cannot
be reproduced elsewhere:

```console
$ git status \
    --porcelain \
    -- . ':(exclude)notes/ontology/<subject>'
```

Pass the real `--out` in place of `notes/ontology/<subject>`. Output means
uncommitted edits: the working tree differs from the commit, so
stop and ask the user to commit or pass a scope that excludes them.

```console
$ git branch --remotes --contains HEAD
```

No output means the commit is not pushed, so a permalink to it can 404. Pin a
pushed ref instead, or record the source without a URL (below).

```console
$ git rev-parse --short HEAD
```

Resolve the ref to the commit it points at, and record that as `commit`, so
`verify` can later tell a moved tag from an unmoved one:

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 --jq .sha
```

For a local checkout, `git rev-parse HEAD` gives the commit. For a remote on
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
  "saved word for word"): state what was recorded.
- "Out of scope" is not a reason in `why`. Say what the source contains and why
  that does not bear on the vocabulary.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <subject>: <n> sources
pinned, <n> skipped` or `⚠ Blocked: <reason>`. Sections:

1. `## Pinned`: the `sources.jsonl` written, as a path under `--out`, then
   each source read, its ref, and how the ref was resolved.
2. `## Skipped`: each source not read, and why.
3. `## Shape`: the inventory that informed the scope decision.

Next-step options: run extract, widen scope, stop here.

Write it per `../../references/prose-rules.md`.
