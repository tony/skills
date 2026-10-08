# Source links

Contents: Link everything that has a URL, Pin every reference into a repository (including Verify a line range), Let GitHub do the linking where it already does, What rots, Primary sources.

How to link so the link still works. The link set for a named
open-source project is in `project-links.md`.

A rotted link is worse than no link: it resolves, looks authoritative,
and points at unrelated code. Write for a three-year horizon.

## Link everything that has a URL

Every project, package, specification, standard, command, error code,
issue, commit, release, and document that names a thing a reader could
look up. The first mention carries the link; later mentions do not
repeat it.

## Pin every reference into a repository

### A release tag first

```
https://github.com/OWNER/REPO/blob/v2.40.0/README.md
```

Most durable; it tells the reader which released version the claim held
for.

### Otherwise a 7-character commit reachable from trunk

```
https://github.com/OWNER/REPO/blob/9a29b1a/src/index.ts
```

Use when there is no tag, or the claim is about unreleased code. Never
a pull-request head — it can be rebased or garbage-collected.

### Never a branch

`blob/main/…` rots silently: the anchor lands on unrelated code while
still returning 200. Reserve it for a living document meant to always
show the latest state, such as a contributing guide.

### Line anchors only on a pinned ref

`#L120` for a line and `#L120-L145` for a range. On a file GitHub
renders rather than displays (markdown, reStructuredText), the anchor
needs `?plain=1` before the fragment or it has nothing to attach to.

```
https://github.com/OWNER/REPO/blob/9a29b1a/README.md?plain=1#L14
```

A line-range permalink renders as a code snippet only inside the
repository it points into, and only in a comment body. Filing across
repositories, quote the lines in a fence next to the link.

When a pin cannot be resolved (no network, no release), keep the
unresolved ref visibly marked in the draft, such as `<SHA>`, and list
it in the reply as unverified. Never substitute a guess.

### Resolving the ref

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

A repository with no releases prints nothing; fall back to the tags:

```console
$ git ls-remote --tags --refs --sort=-v:refname https://github.com/OWNER/REPO
```

Version sort ranks `v1.2.0-rc1` above `v1.2.0`; read the list, do not
take the first line.

A tag pins content only by convention: git allows a tag to be moved.
When the link is evidence for a quoted line, resolve it to a commit:

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 --jq .sha
```

That endpoint resolves lightweight and annotated tags alike. Do not use
`git/ref/tags/<tag>`: on an annotated tag it returns the tag object's
SHA, and a blob URL built on it 404s.

### Verify a line range

A range the user took from `main` can cover other code at the pinned
ref. Fetch the file at that ref, print the range, and confirm the named
symbol lies in it:

```console
$ gh api 'repos/OWNER/REPO/contents/PATH?ref=REF' \
    -H 'Accept: application/vnd.github.raw' \
    | sed -n '38,50p'
```

When the symbol is outside the range, find its lines in this output and
use them; when it is gone, drop the anchor or ask the user. Never publish
a range you did not read at the ref.

Confirm before publishing:

```console
$ curl -s \
    -o /dev/null \
    -w '%{http_code}\n' \
    -L \
    'https://github.com/OWNER/REPO/blob/v2.40.0/README.md'
```

## Let GitHub do the linking where it already does

Inside issue, pull request, discussion, and comment bodies; not in
repository files or wikis.

### Same repository: write the bare reference

`#123` for an issue or pull request, and a 7-character commit ref for
a commit. Both autolink with no markdown syntax. Issues and pull
requests share one number space, so `#123` may land on either — do not
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

- [Creating a permanent link to a code snippet](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet) — snippet rendering scope, `?plain=1`
- [Autolinked references and URLs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls)
- [REST: autolinks](https://docs.github.com/en/rest/repos/autolinks) — admin only
- [REST: Git references](https://docs.github.com/en/rest/git/refs)
- [Renaming a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository) — redirects, and what breaks them
- [Renaming a branch](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/renaming-a-branch)
- [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
