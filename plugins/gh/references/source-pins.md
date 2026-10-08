<!-- Vendored from shared/source-pins.md; edit that file, then run 'scripts/marketplace.py portable'. -->
# Source pins

## Pin repository evidence

Prefer a release tag, such as `blob/v2.40.0/README.md`. Otherwise use a
7-character commit reachable from trunk, such as `blob/9a29b1a/src/index.ts`.
Never use a pull-request head: it can be rebased or garbage-collected.

Use `blob/main/…` only for a living document meant to show the latest state,
such as a contributing guide. That link is a navigation pointer, not evidence
for a claim about file contents.

Put line anchors only on a pinned ref: `#L120` for one line or `#L120-L145`
for a range. GitHub-rendered Markdown and reStructuredText need `?plain=1`
before the fragment:

```text
https://github.com/OWNER/REPO/blob/9a29b1a/README.md?plain=1#L14
```

If a pin cannot be resolved, leave a visible placeholder such as `<SHA>` in
the draft and report it as unverified. Never substitute a guessed ref.

## Resolve the ref

List the newest published stable release of a repository not cloned locally:

```console
$ gh release list \
    --repo OWNER/REPO \
    --limit 1 \
    --exclude-drafts \
    --exclude-pre-releases \
    --json tagName \
    --jq '.[0].tagName'
```

If that prints nothing, inspect the tags:

```console
$ git ls-remote \
    --tags \
    --refs \
    --sort=-v:refname \
    https://github.com/OWNER/REPO
```

Version sort can rank a prerelease above its stable release. Read the list;
do not take the first line without checking.

Tags can move. For evidence supporting a quotation, resolve the tag to a
commit and retain that commit with the citation:

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 \
    --jq .sha
```

This endpoint resolves both lightweight and annotated tags. The
`git/ref/tags/<tag>` endpoint can return an annotated tag object's SHA,
which is not the commit needed for a blob link.

## Verify the cited contents

A line range from a branch may cover different text at the pinned ref.
Read the file at that ref and confirm the cited symbol and quotation:

```console
$ gh api 'repos/OWNER/REPO/contents/PATH?ref=REF' \
    -H 'Accept: application/vnd.github.raw' \
    | sed -n '38,50p'
```

If the symbol is outside the range, use its lines at this ref. If it is
absent, drop the anchor or ask the user. Never publish an unread range.

Confirm the URL serves the intended file, not an error or login page:

```console
$ curl -s \
    -o /dev/null \
    -w '%{http_code}\n' \
    -L \
    'https://github.com/OWNER/REPO/blob/v2.40.0/README.md'
```

## Primary sources

- [Permanent links to code snippets](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet)
- [Git references API](https://docs.github.com/en/rest/git/refs)
