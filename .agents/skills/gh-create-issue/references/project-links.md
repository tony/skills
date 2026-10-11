# Project links

Read this only when the text names an upstream open-source project.
Package-registry lookups are in `registry-links.md`, which
`create-issue` loads. Pinning rules for each link are in `source-links.md`.

On first mention, link the project to its primary home, and add only the
links the claim depends on: the changelog at the release for a claim about
a version, the repository for a claim about code, the documentation for a
claim about documented behavior, the registry page for a claim about
packaging. Research each; do not reconstruct URLs from memory (project and
version below are illustrative):

```
[vitest](https://vitest.dev): [v1.6.0 release notes](https://github.com/vitest-dev/vitest/releases/tag/v1.6.0)
```

A slot that does not exist is left out, never pointed at the same page as
another.

Confirm the repository itself; a registry records what was true at publish
time:

```console
$ gh repo view OWNER/REPO --json url,homepageUrl,description,isArchived
```

## Changelog at the release, never at trunk

```
https://github.com/OWNER/REPO/releases/tag/v2.40.0
```

Copy `html_url` from the API rather than building the URL:

```console
$ gh api repos/OWNER/REPO/releases/tags/v2.40.0 --jq '{tag_name, html_url}'
```

`/releases/latest` is the most recent non-prerelease, non-draft release
and moves as releases are published; never use it for a claim about a
specific version. When a project publishes no releases, link a tag-pinned
`CHANGELOG` file, or a `/compare/<old>...<new>` URL.

## Primary sources

- `gh repo view --help` and `gh release view --help`
- [REST: releases](https://docs.github.com/en/rest/releases/releases): "latest release"
