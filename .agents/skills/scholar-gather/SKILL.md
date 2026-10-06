---
name: scholar-gather
description: >-
  Resolve and pin a corpus, inventory it, and record what was read and what
  was deliberately skipped, into sources.jsonl
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion", "WebFetch"]
metadata:
  argument-hint: "<target>... [--kind=code|prose|fleet] [--out=<dir>]"
  source: "plugins/scholar/skills/gather/SKILL.md"
---

# this skill

Stage 1. Turn a loose target — a repository, a set of them, a book — into a
pinned, inventoried source list a later stage can cite against.

Read `references/citation.md` for how to pin, and
`references/stage-gates.md` for this stage's exit condition.

User arguments: $ARGUMENTS

## The invariant

Never write into the corpus being read: no `git checkout`, no `git clean`, no
edit inside a target. Studying a project must not dirty its checkout. Output
lands under `--out`, defaulting to `notes/ontology/<subject>/` in the current
repository. The corpus is recorded by URL and ref, not by local path.

## Procedure

### 1. Survey the workspace

Run `git remote get-url origin` to name the current repository; a failure
means the working directory is not a git repository. Run `ls notes/ontology/`
to list existing studies; a failure means there are none.

### 2. Resolve each target to a ref

For a git repository, prefer a release tag; fall back to a 7-character commit
reachable from trunk. Never a branch name — it moves, and every citation built
on it rots silently.

Newest tag of a repository you have not cloned:

```console
$ gh release list --repo OWNER/REPO --limit 1 --exclude-drafts --exclude-pre-releases --json tagName --jq '.[0].tagName'
```

A repository can have thousands of tags and no releases, in which case that
prints nothing. Fall back to the tags:

```console
$ git ls-remote --tags --refs --sort=-v:refname https://github.com/OWNER/REPO
```

For a local checkout, record both the remote and the exact ref:

```console
$ git rev-parse --short HEAD
```

For prose, the ref is the edition: publisher, year, and printing.

### 3. Inventory without reading everything

Establish the shape of the corpus cheaply. For code, the module or package
list and the size of each. For prose, the table of contents. For a fleet, the
repository list and what each one is for.

The inventory is what makes the coverage decision in step 4 an informed one
rather than a guess.

### 4. Decide scope with the user

Present the inventory via `ask-user-choice` and settle what will be read. Most
studies should not read everything; the point is to decide deliberately rather
than to run out of attention silently.

### 5. Write sources.jsonl

One row per source, including every source deliberately not read:

```
{"source": "https://github.com/OWNER/REPO", "ref": "v2.40.0", "scope": "src/parser/", "read": true, "why": ""}
{"source": "https://github.com/OWNER/REPO", "ref": "v2.40.0", "scope": "test/", "read": false, "why": "tests name fixtures, not domain concepts"}
```

A study that does not state its coverage boundary is not honest about what it
does not know. `contest`'s completeness pass reads exactly this file.

## Rules

- "Out of scope" is not a reason in `why`. Say what the source contains and why
  that does not bear on the vocabulary.

## Output

Per `references/output-contract.md`. Hero: `✓ <subject>: <n> sources
pinned, <n> skipped` or `⚠ Blocked: <reason>`. Sections:

1. `## Pinned` — each source read, its ref, and how the ref was resolved.
2. `## Skipped` — each source not read, and why.
3. `## Shape` — the inventory that informed the scope decision.

Next-step options: run extract, widen scope, stop here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
