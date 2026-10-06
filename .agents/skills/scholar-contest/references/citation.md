# Citation

How to pin a source so the citation still works in three years, and what a
citation has to carry before it counts as evidence.

## Pin every reference

**A release tag first.** `blob/v2.40.0/README.md`. Most durable, and it tells
the reader which released version the claim held for.

**Otherwise a 7-character commit reachable from trunk.** `blob/9a29b1a/src/x.ts`.
Use when there is no tag, or the claim is about unreleased code. Never a
pull-request head: it can be rebased or garbage-collected.

**Never a branch.** `blob/main/…` rots silently. The file moves, the lines
shift, and the anchor lands on unrelated code while still returning 200. The
one exception is a living document meant to always show the latest state, such
as a contributing guide; link it as a pointer, never as evidence for a claim.

**Line anchors only on a pinned ref.** `#L120` for a line, `#L120-L145` for a
range. On a file the host renders rather than displays — Markdown,
reStructuredText — the anchor needs `?plain=1` before the fragment or it has
nothing to attach to.

Resolve a tag to the commit it points at, so a moved tag cannot silently
change what a quotation says:

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 --jq .sha
```

Confirm a URL resolves before writing it down:

```console
$ curl -s -o /dev/null -w '%{http_code}\n' -L 'https://github.com/OWNER/REPO/blob/v2.40.0/README.md'
```

## Every citation carries a locator

A citation names where in the source the claim lives, not just which source.
Take the most stable locator the source supports, in this order:

1. Code or text in version control: a line range on a pinned ref, which
   `verify` can check mechanically.
2. Structured prose: chapter and section. It survives repagination and
   translation.
3. A book: a page, and only where `sources.jsonl` records the edition. A page
   number without an edition is true of one printing only.
4. A source with no stable anchor, such as a PDF without pagination or a
   transcript: quote enough unique text to be found by search, and record in
   `sources.jsonl` that the locator is a search string rather than a position,
   so `verify` checks it by search.

Never invent a position the source does not have. A confident wrong locator
costs a reader more than an honest search string.

## Circular evidence does not count

A citation whose quoted text contains the term it supports proves nothing. It
shows the corpus uses the word, which was never in question, and hides whether
the corpus uses it the way the definition claims.

`term-metrics.py` reports these as `circular evidence`. Replace the quotation
with one that shows the term in use without naming it, or mark the term as
resting on a definition the corpus states directly.
