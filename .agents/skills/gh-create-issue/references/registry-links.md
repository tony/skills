# Registry links

Optional. Read this only when the user asks for, or the claim needs, a
package-registry link; `project-links.md` covers every other link. Every
`curl` uses `-f`, so a 404 fails instead of reaching `jq` as data.

## Resolving links from a registry

npm, including `repository.directory` for a package inside a monorepo:

```console
$ curl -fsS 'https://registry.npmjs.org/PKG/latest' | jq '{version, homepage, repository, bugs}'
```

PyPI, where the link set is maintainer-labeled free text:

```console
$ curl -fsS 'https://pypi.org/pypi/PROJECT/json' \
    | jq '.info | {package_url, home_page, project_urls}'
```

crates.io, whose policy requires a user agent that identifies the
application and caps API use at one request per second. Use this fixed
string, which names this plugin and its repository, not the user:

```console
$ curl -fsS \
    -A 'tony-skills-gh-plugin (https://github.com/tony/skills)' \
    'https://crates.io/api/v1/crates/CRATE' \
    | jq '.crate | {homepage, documentation, repository, default_version}'
```

RubyGems exposes `changelog_uri`:

```console
$ curl -fsS 'https://rubygems.org/api/v1/gems/GEM.json' \
    | jq '{homepage_uri, source_code_uri, documentation_uri, changelog_uri}'
```

Go, resolving version, tag ref, and commit in one call. The module path is
case-encoded for the proxy (each uppercase letter becomes `` ! `` and its
lowercase), which `goencode` prints:

```console
$ python3 /absolute/path/to/scripts/issue.py goencode MODULE
```

```console
$ curl -fsS 'https://proxy.golang.org/ENCODED_MODULE/@latest'
```

## What rots in registry data

- A registry-recorded repository URL can predate a rename; it resolves
  only through that redirect.
- `npm` `repository.url` is a VCS URL (`git+https://….git`), not a
  browsable link. `homepage` is often just the README anchor.

## Primary sources

- [PyPI JSON API](https://docs.pypi.org/api/json/)
- [RubyGems API](https://guides.rubygems.org/rubygems-org-api/)
- [Go modules reference, GOPROXY protocol](https://go.dev/ref/mod#goproxy-protocol): case encoding
- [npm `package.json` `repository`](https://docs.npmjs.com/cli/v10/configuring-npm/package-json#repository)
- [crates.io data access policy](https://crates.io/data-access) and [RFC 3463](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html): user-agent and rate rules
