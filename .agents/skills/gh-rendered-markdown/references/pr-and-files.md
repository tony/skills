# Pull requests and repository files

Rules that differ from an issue or comment body. Read this only when the
text is a pull-request description or a repository markdown file; `rendered-markdown.md` holds the rules every surface
shares.

## Pull requests

Describe the branch's net change, not the route it took; the commits
already carry renames, reverted attempts, and fixups.

The `Keep out of the record` list in `prose-rules.md` applies.

A pull-request body follows the comment-body rules in
`rendered-markdown.md`.

## Repository files

A single newline in a markdown file is a soft line break, which the
[GFM spec](https://github.github.com/gfm/#soft-line-breaks) renders as a
space, so wrapping does not change the output. Match whatever the repository already does;
never re-wrap a file because a body nearby is unwrapped.

A file keeps its `#` title heading. To reference an issue from a file, use
the full URL, which does not depend on a renderer's autolinking.
