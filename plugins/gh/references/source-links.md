# Source links

How to link so the link still works. The link set for a named
open-source project is in `project-links.md`.

A rotted link is worse than no link: it resolves, looks authoritative,
and points at unrelated code. Write for a three-year horizon.

## Link everything that has a URL

Every project, package, specification, standard, command, error code,
issue, commit, release, and document that names a thing a reader could
look up. The first mention carries the link; later mentions do not
repeat it.

## Let GitHub do the linking where it already does

Inside issue, pull request, discussion, and comment bodies; not in
repository files or wikis.

A line-range permalink renders as a code snippet only inside the repository
it points into, and only in a comment body. Filing across repositories,
quote the lines in a fence next to the link.

### Same repository: write the bare reference

`#123` for an issue or pull request, and a 7-character commit ref for
a commit. Both autolink with no markdown syntax. Issues and pull
requests share one number space, so `#123` may land on either; do not
assert which in prose.

Wrapping a reference in `[text](url)` suppresses the shortening;
wrapping it in backticks suppresses the link. Use both deliberately.

### Another repository: link it explicitly

```
[REPO#123](https://github.com/OWNER/REPO/issues/123)
```

The explicit form also survives in a repository file, a non-GitHub
tracker, or a body someone copies elsewhere.

### Tracker keys: check whether the repository resolves them

A key like `TIK-111` renders as plain text unless a repository admin
configured a custom autolink for that prefix. When it is configured,
write the bare key. When it is not, write a full markdown link.

`GET /repos/{owner}/{repo}/autolinks` needs admin and returns 404 for
everyone else, the same as "none configured". Render the token instead;
the preview applies the repository's real autolinks:

```console
$ gh api --method POST /markdown -f mode=gfm -f context=OWNER/REPO -f text='TIK-111'
```

### Unresolvable references render as plain text

A wrong issue number or a SHA that is not in the repository produces
no link and no error. Confirm anything you did not copy from a live
page.

## What rots

- A repository rename redirects, until someone re-creates the old name
  under the old owner. Then it silently points somewhere else.
- A branch rename redirects normal URLs.
- Unauthenticated GitHub API calls are capped at 60 per hour per IP.
  Route them through `gh`.

## Primary sources

- [Creating a permanent link to a code snippet](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet): snippet rendering scope, `?plain=1`
- [Autolinked references and URLs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls)
- [REST: autolinks](https://docs.github.com/en/rest/repos/autolinks): admin only
- [REST: Git references](https://docs.github.com/en/rest/git/refs)
- [Renaming a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository): redirects, and what breaks them
- [Renaming a branch](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/renaming-a-branch)
- [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
