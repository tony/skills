# Project links

Read this only when the text names an upstream open-source project.
Pinning rules for each link are in `source-links.md`.

On first mention, give the whole set: repository, homepage,
documentation, the changelog at the release in question, and the
package-registry page. Research it; do not reconstruct URLs from memory.
Render the project name linked to its primary home, with the rest
alongside (project and version below are illustrative):

```
[vitest](https://vitest.dev) — [repo](https://github.com/vitest-dev/vitest), [docs](https://vitest.dev/guide/), [v1.2.3 release notes](https://github.com/vitest-dev/vitest/releases/tag/v1.2.3), [npm](https://www.npmjs.com/package/vitest)
```

Drop a slot that genuinely does not exist rather than pointing two
slots at the same page.

## Resolving the set from a registry

npm, including `repository.directory` for a package inside a monorepo:

```console
$ curl -s https://registry.npmjs.org/PKG/latest | jq '{version, homepage, repository, bugs}'
```

PyPI, where the link set is maintainer-labeled free text:

```console
$ curl -s https://pypi.org/pypi/PROJECT/json | jq '.info | {package_url, home_page, project_urls}'
```

crates.io, which requires an identifying user agent that includes a contact (replace `CONTACT` with the user's project URL or email, and ask first):

```console
$ curl -s -A 'issue-authoring (CONTACT)' https://crates.io/api/v1/crates/CRATE | jq '.crate | {homepage, documentation, repository, default_version}'
```

RubyGems exposes `changelog_uri`:

```console
$ curl -s https://rubygems.org/api/v1/gems/GEM.json | jq '{homepage_uri, source_code_uri, documentation_uri, changelog_uri}'
```

Go, resolving version, tag ref, and commit in one call:

```console
$ curl -s https://proxy.golang.org/MODULE/@latest
```

Second-source the repository itself, since a registry records what was
true at publish time:

```console
$ gh repo view OWNER/REPO --json url,homepageUrl,description,isArchived
```

## Changelog at the release, never at trunk

```
https://github.com/OWNER/REPO/releases/tag/v2.40.0
```

Copy that URL from the API rather than building it: monorepo tags carry
prefixes and encodings not derivable from a version number
(`@changesets/cli@2.31.1` becomes `%40changesets/cli%402.31.1`, Go
submodules tag as `module1/v1.2.3`).

```console
$ gh api repos/OWNER/REPO/releases/tags/v2.40.0 --jq '{tag_name, html_url}'
```

`/releases/latest` moves on every publish and means different things in
the API and the web UI; never use it for a claim about a specific
version. When a project publishes no releases, link a tag-pinned
`CHANGELOG` file, or a `/compare/<old>...<new>` URL.

## What rots in registry data

- A registry-recorded repository URL can predate a rename; it resolves
  only through that redirect.
- `npm` `repository.url` is a VCS URL (`git+https://….git`), not a
  browsable link. `homepage` is often just the README anchor.
- Registry web pages reject non-browser clients — npmjs.com and
  crates.io both return 403 to `curl`, crates.io citing its data
  access policy. Validate those through the JSON APIs above, not with
  a status check.
