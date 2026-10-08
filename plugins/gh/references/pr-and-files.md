# Pull requests, repository files, and commit messages

Rules that differ from an issue or comment body. Read this only when the
text is a pull-request description, a repository markdown file, or a
commit message; `rendered-markdown.md` holds the rules every surface
shares.

## Pull requests

Describe the branch's net change, not the route it took; the commits
already carry renames, reverted attempts, and fixups.

Leave out:

- Renames of symbols that never shipped.
- "Previously X" framing for behavior no released user saw.
- Any paraphrase of the diff.

A pull-request body is rendered like a comment body: never hard-wrap it.
Start its headings at `###`.

## Repository files

A single newline in a markdown file is a soft line break, which the
[GFM spec](https://github.github.com/gfm/#soft-line-breaks) renders as a
space, so wrapping does not change the output. Match whatever the repository already does;
never re-wrap a file because a body nearby is unwrapped.

A file keeps its `#` title heading. To reference an issue from a file, use
the full URL, which does not depend on a renderer's autolinking.

## Commit messages

They are not rendered markdown at all, and they wrap. The project's own
commit convention governs.
