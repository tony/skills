# Action pinning and tag verification

Read before writing any version string into a workflow.

## Contents

- Scope
- Inventory pins from trunk, not the working tree
- Resolve the latest version
- List the majors between the pin and the target
- Verify the target tag exists
- Dereference annotated tags before comparing
- Resolve a tag to its commit SHA
- Choose the pin, preserving the repo's shape
- Check the gates the research surfaces

## Scope

Own repositories only. Check the fork flag, not the owner name:

```console
$ gh repo view <owner>/<name> --json isFork
```

A fork (`isFork: true`) is out of scope unless the user names it with
`--repo`. Report which repositories were excluded and why.

## Inventory pins from trunk, not the working tree

Resolve the default branch from the API (`origin/HEAD` may be unset), then
fetch so `origin/<default>` is current; without the fetch, say the audit may
be stale.

```console
$ gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
```

```console
$ git fetch origin
```

Read workflow content from `origin/<default>`, not the checkout. Cover
`.github/workflows/**` and `.github/actions/**`; composite actions pin
versions too and are the most often missed.

Loop over the file list with `while read -r`: an unquoted captured list
expands as one word in zsh, so a repo with two workflow files drops out of
the audit with no error and the fleet reads as clean.

```bash
git ls-tree -r --name-only origin/<default> .github | while read -r f; do
  git show "origin/<default>:$f" | grep -n -E '^[[:space:]]*-?[[:space:]]*uses:' | sed "s|^|$f:|"
done
```

Skip `uses: ./path` (local) and `uses: docker://...` (no tag to verify)
and say so in the report. For `owner/repo/subpath@ref`, look up tags on
`owner/repo`. On a host other than github.com, set `GH_HOST` and use
that host's URL for `git ls-remote`.

## Resolve the latest version

Ask the registry, not memory:

```console
$ gh api repos/<owner>/<action>/releases/latest --jq .tag_name
```

Some actions publish only tags; list refs when `releases/latest` returns
nothing. `releases/latest` is the most recently published release, which
can be a backport on an older major line; compare it against the highest
major in the list below before calling it the target.

## List the majors between the pin and the target

A major's first release is its `vN.0.0` tag. List them all, then keep
those above the pin's major and at or below the target's:

```console
$ gh api repos/<owner>/<action>/releases \
    --paginate \
    --jq '.[].tag_name | select(test("^v[0-9]+\\.0\\.0$"))'
```

For `actions/checkout` v3 to v7 this prints `v7.0.0` through `v1.0.0`;
keep `v4.0.0`, `v5.0.0`, `v6.0.0`, and `v7.0.0`. An action with no
`vN.0.0` release tags its majors as bare `vN`: list them with `git
ls-remote --tags` and take the first release of each major from the tags.
Link each kept tag only after the release-URL check passes.

## Verify the target tag exists

Confirm before writing, and gate on exit status:

```console
$ gh api repos/<owner>/<action>/git/ref/tags/<tag> >/dev/null 2>&1
```

Piping `gh api` into `jq` or `sed` first swallows the 404 and reports a
missing tag as present. Not every action publishes a floating major; run
the same check against `git/ref/tags/v<major>` before choosing a float.

## Dereference annotated tags before comparing

`.object.sha` on an annotated tag is the tag object, not the commit, so
comparing two tags by it makes identical tags look different. Dereference
when the type is `tag`:

```console
$ gh api repos/<owner>/<action>/git/tags/<tag-object-sha> --jq .object.sha
```

This confirms claims like "the floating v6 tag now points at the v7 commit",
which decide whether a bump is a behaviour change or a label correction.

## Resolve a tag to its commit SHA

A SHA pin needs the commit, not the tag object. Ask for the tag and its
peeled form together: an annotated tag prints two lines (the `^{}` line is
the commit), a lightweight tag one. `tail -n 1` takes the right line:

```console
$ git ls-remote \
    https://github.com/<owner>/<action>.git \
    "refs/tags/<tag>" \
    "refs/tags/<tag>^{}" \
    | awk '{print $1}' \
    | tail -n 1
```

An empty result means the tag does not exist; stop.

## Choose the pin, preserving the repo's shape

Default to the major-level float: it collects patches without a commit per
patch release.

**Currently a major float** (`@v6`) — move to the next major float
(`@v7`).

**Currently an exact patch** (`@v4.0.1`) — repin to the float (`@v4`)
when it exists and resolves to at least that patch. Say `repin X -> Y`
in the subject; "from 4.0.1 to 4" reads as a downgrade otherwise.

**Currently a commit SHA with a version comment** — move the SHA *and* the
trailing comment together; a stale `# v8.1.0` beside a v9 SHA is worse than
no comment.

**Currently a moving branch** (`@main`, `@master`) — leave it and report
it as drift; bump it only when the user names a target.

**No major tag upstream** — pin the exact release and say why in the commit
body, so no one "fixes" it to a float that does not exist.

## Check the gates the research surfaces

Before writing a body that claims an upgrade is safe, grep the actual
workflows for each breaking change the release notes name:

- Removed or renamed inputs, and changed defaults.
- `pull_request_target` or `workflow_run` combined with an explicit
  `ref:` or `repository:` pointing at fork data.
- A new runtime requirement. Self-hosted `runs-on` values gate every
  bump to a newer Node runtime.
- Package-manager declaration and lockfile requirements.

A fleet-wide fact is not a per-repo fact: where a general claim ("this repo
authenticates via OIDC") does not hold, override the body for that repo.
