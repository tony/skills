---
name: rebuild
description: "Use when rebuilding a bloated tracker item whose epic or Jira ticket hard-codes implementation, restates a spec, or cites counts and line numbers."
user-invocable: true
argument-hint: "[URL or identifier]"
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "AskUserQuestion"]
---

# Rebuild a ticket

Rebuild one live tracker item against the content contract. Not a trim — a
rebuild, at the altitude the item should have been written at.

Argument: `$ARGUMENTS` — a URL, an identifier, or nothing (then ask).

## Read first

- `../../references/contract.md` — the three tenses.
- `../../references/altitude.md` — which sections each kind of object carries.
- `../../references/resolve.md` — how to establish the provider and role, and
  the index of provider files.
- Only the matched provider's file from that index — reference syntax, read
  and write mechanics.
- `../../references/hierarchy.md` only when the role is ambiguous or a native
  noun collides across providers.

## Core principle

Nothing valuable is deleted. It is kept, relocated, or demoted.

An overgrown ticket is usually not padded. It is a document, a research note,
and a work item that got filed as one object. The fix is to separate them,
not to compress them.

## Phase 1 — Fetch and preserve

Resolve the provider and identifier per `resolve.md`, then fetch the live
item with its comments. Comments matter: the decision that supersedes the
body is often in one.

Save the original body to a private scratch file outside the working tree
before touching anything. The body may hold secrets or personal data, so
restrict the file and remove it when the run ends, whether or not the user
confirms. Shell state does not persist between calls: print the path once and
use the literal path afterwards.

```console
$ umask 077 && mktemp "${TMPDIR:-/tmp}/ticket-original.XXXXXX"
```

Some providers keep edit history and some do not. Do not rely on the tracker
to hold your undo.

## Phase 2 — Resolve the altitude it should be

Establish the current semantic role, then ask whether the content matches it.
A `work_item` carrying a nine-section design is a `delivery_group` plus a
`document` that were filed as one issue.

The altitude the item *should* be is the finding, not a detail. State it.

## Phase 3 — Audit

Classify every part of the existing body into exactly one bucket. Do not skip
this into a rewrite; the buckets are what you show the user.

**Keep.** Passes the cost-to-relearn filter — a measurement with its
conditions, a dead end with its reason, a retracted number with what was
actually measured, an absorbed-item list with why each folded in, a live
blocker that changes what happens first. Also keep load-bearing links.

**Cut.** Recoverable from the repository. File sizes, insertion counts, line
counts, test counts, what got renamed, which module was split, how long a
draft was. Also the sequence of hypotheses that led to a finding, and any
narration of revisions that happened before the item was published.

**Relocate.** Valuable, but not at this altitude. A design restated from an
ADR, a research pass with prior-art citations, an implementation sketch. This
goes to a `document`, and the item links to it. Offer to create the document
where the provider has one, or to write it into the repository where it does
not.

**Demote.** Future-tense content that is not existential. A definition-of-done
checklist becomes a small set of invariants plus intent labelled non-binding.
Most checklist items demote; a couple survive as invariants; any that encode
a technical decision are cut outright and the reasoning goes to intent.

**Repair.** References that rot or misfire — `blob/main` links, line anchors
on unpinned refs, bare cross-container references, bare identifiers that are
ambiguous out of context. Rewrite them per the two-axis rule and the provider
file. Re-saving a body can re-fire every reference in it, so check the
provider file before assuming an edit is silent.

## Phase 4 — Find what is missing

Most overgrown items are also missing something. Check for all of these:

- No invariants at all, because everything was stated as a requirement.
- An outcome that never says what changes for whom.
- Evidence asserted without a reproduction or a version.
- Children or absorbed items referenced in prose but never linked.
- A superseding decision that lives only in a comment. Comments are never
  rewritten, so report it under Missing and propose carrying it into the body.

Absence is a finding. Report it with the rest.

## Phase 5 — Rebuild

Write the new body from the audit, not by editing the old text. Take the
section list from `altitude.md` for the role the item should be.

Then check the future tense against `contract.md`.

Sanitize for local paths, hostnames, emails, tokens, and internal URLs.

Write it per `../../references/prose-rules.md`.

Save the new body to a scratch file created the same way, so Phase 7 passes
it from a file.

Render the new body the way the provider will.

## Phase 6 — Present

Lead with the result and stop at the last concrete point, with no recap. Use
plain prose and nested lists, no tables, and no bold label on every bullet.
Do not name scratch-file paths. Show, in this order:

1. A hero line: the role it is and the role it should be. No bucket counts.
2. `## Kept` — what survived, and why each item could not be re-derived.
3. `## Cut` — what went, grouped by reason.
4. `## Relocated` — what moved, and where it is going.
5. `## Demoted` — the old definition of done, then the new invariants.
6. `## Missing` — what the item never had.
7. `## Rebuilt title and body` — the full title and body.

A halted run (no readable item, unsanitizable evidence) is one result
sentence, then what the user needs to do.

Then offer, via `AskUserQuestion`: update the item, update and also create the
relocated document, print the body only, revise a named section, or drop it.
Where no interactive question tool exists, print the result and stop; an
update needs an explicit instruction naming the action.

## Phase 7 — Update

Only on explicit approval, and only through the provider's documented write
path with the body passed from a file.

Where no write backend exists, print the approved body to paste and say that
is what is happening.

When a document was relocated, create it first and land its link in the
rebuilt body before the item is updated, so the item never points at
something that does not exist yet.

Report the URL, then remove both scratch files.

## Rules

- One item per run. No bulk passes.
- Never update without showing the bucket breakdown and the full rebuilt body.
- Never delete content that belongs in the relocate bucket. If the user
  declines the document, keep the content in place and say it is staying.
- Never rewrite comments, only the body. Comments are other people's words.
- Never close, reassign, relabel, or reparent the item. Rewriting a body is
  the whole mandate.
- Never invent a reference syntax or a link that was not verifiable.
