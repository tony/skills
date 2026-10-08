# Citation

How to pin a source so the citation still works in three years, and what a
citation has to carry before it counts as evidence.

Record the resolved commit of a repository ref as `commit` in `sources.jsonl`;
`verify` compares it against the ref later to detect moved tags.

## Every citation carries a locator

A citation names where in the source the claim lives, not just which source.
The source row's `locator_kind` says what the cite's `locator` holds, and is
one of these four values in every stage. Take the most stable the source
supports, in this order:

1. `line-range`: code or text in version control, as a line range on a pinned
   ref. `verify` checks it mechanically.
2. `section`: structured prose, as chapter and section. It survives
   repagination and translation.
3. `page`: a book page, only where `sources.jsonl` records the edition. A page
   number without an edition is true of one printing only.
4. `search-string`: a source with no stable anchor, such as a PDF without
   pagination or a transcript. The `locator` is enough unique text to be found
   by search, and `verify` checks it by search.

A source with no remote has no permalink. Publish it first; otherwise cite it
as `path@commit` with no `url`, and `verify` checks it with `git show`.

Never invent a position the source does not have. A confident wrong locator
costs a reader more than an honest search string.

## The cite fields

Every entry in a row's `cites` carries these fields:

- `source`: the `source` value of the cite's row in `sources.jsonl` (a
  repository URL, or the id `gather` gave a prose document). It ties the cite
  to the pinned ref or edition, and `verify` reads it.
- `locator`: where in the source, in the row's `locator_kind`.
- `quote`: the text at that locator.
- `url`: the pinned permalink, for a source with a remote. A prose source has
  no `url`; a cite is `source`, `locator`, `quote`.

## Circular evidence does not count

A citation whose quoted text contains the term it supports proves nothing. It
shows the corpus uses the word, which was never in question, and hides whether
the corpus uses it the way the definition claims.

`term_metrics.py` reports these as `circular evidence`. Replace the quotation
with one that shows the term in use without naming it, or mark the term as
resting on a definition the corpus states directly.
