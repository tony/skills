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
$ gh repo view \
    --json isFork \
    https://github.com/<owner>/<name>
```

A fork (`isFork: true`) is out of scope unless the user names it with
`--repo`. Report which repositories were excluded and why.

## Inventory pins from trunk, not the working tree

Pin reads name their repository and host: `git -C <path>` for a clone,
`gh repo view https://github.com/<slug>` and
`gh api --hostname github.com repos/<slug>/...` for the API. The working
directory and inherited `GH_HOST` or `GH_REPO` must not select the target.

`references/pins.py` does this deterministically (Python 3.9 or newer). It
resolves the remote (`origin`, else the only remote), requires one declared
HTTPS or SSH URL whose hostname is exactly `github.com`, then fetches and
reads the default branch from the API. Git URL rewrites and SSH configuration
can redirect transport; this check validates the declared URL only.
It prints one JSON object per repository with
every `uses:` pin in workflow and composite-action YAML files. Print the
script's absolute path once and write it literally in each command:

```console
$ python3 <absolute-path>/pins.py inventory <path-or-slug> [<path-or-slug>...]
```

A repository named only by slug (`--repo <owner>/<name>` with no local
clone) is read through the API. Without a local clone nothing can be
committed: report that repository's audit and skip its commits, unless the
user supplies a checkout path. Without the script, validate the declared
remote URL before fetching, then read each repository explicitly:

```console
$ gh repo view \
    --json defaultBranchRef \
    --jq .defaultBranchRef.name \
    https://github.com/<slug>
```

```console
$ git -C <path> fetch <remote>
```

```console
$ git -C <path> ls-tree \
    -r \
    --name-only \
    <remote>/<default> \
    .github
```

Read only `.github/workflows/*.yml|yaml` and `.github/actions/**/*.yml|yaml`
(composite actions pin versions too and are the most often missed), each with
`git -C <path> show <remote>/<default>:<file>`. Search those files only: a
search over all of `.github` also hits markdown. For a slug, list the tree
with `gh api --hostname github.com "repos/<slug>/git/trees/<default>?recursive=1"` and read each
file raw with `gh api --hostname github.com -H "Accept: application/vnd.github.raw+json"
"repos/<slug>/contents/<path>?ref=<default>"`. Loop with `while read -r`:
an unquoted captured list expands as one word in zsh, so a repo with two
workflow files drops out of the audit with no error and the fleet reads as
clean.

Skip `uses: ./path` (local) and `uses: docker://...` (no tag to verify)
and say so in the report. For `owner/repo/subpath@ref`, look up tags on
`owner/repo`. `pins.py` and the commands here work on github.com only.

## Resolve the latest version

Ask the registry, not memory:

```console
$ gh api \
    --hostname github.com \
    --jq .tag_name \
    repos/<owner>/<action>/releases/latest
```

Some actions publish only tags; when `releases/latest` returns nothing,
list them with `git ls-remote --tags --refs
https://github.com/<owner>/<action>.git` and take the highest. `releases/latest` is the most recently published release, which
can be a backport on an older major line; compare it against the highest
major in the list below before calling it the target.

## List the majors between the pin and the target

`python3 <absolute-path>/pins.py majors <owner/action> <pin> <target>`
prints the first release of each major above the pin and at or below the
target, falling back to the tag list when there are no release objects.
Pass the version from the pin's trailing comment, not the SHA.
By hand: a major's first release is its `vN.0.0` tag. List them all, then keep
those above the pin's major and at or below the target's:

```console
$ gh api \
    --hostname github.com \
    --paginate \
    --jq '.[].tag_name | select(test("^v[0-9]+\\.0\\.0$"))' \
    repos/<owner>/<action>/releases
```

For an action pinned at v3 with a v6 target, keep `v4.0.0`, `v5.0.0`, and
`v6.0.0` from whatever the list prints. An action with no
`vN.0.0` release tags its majors as bare `vN`: list them with `git
ls-remote --tags` and take the first release of each major from the tags.
Link each kept tag only after the release-URL check passes.

## Verify the target tag exists

Confirm before writing, and gate on exit status
(`python3 <absolute-path>/pins.py tag <owner/action> <tag>` does the same
and exits 1 when the tag is missing, 3 when the lookup failed):

```console
$ gh api \
    --hostname github.com \
    repos/<owner>/<action>/git/ref/tags/<tag> >/dev/null 2>&1
```

Only an HTTP 404 means the tag is missing. An auth, rate-limit, or network
failure (`pins.py tag` exit 3) means the tag could not be checked: report
that, never "missing", and do not write the pin.

Piping `gh api` into `jq` or `sed` first swallows the 404 and reports a
missing tag as present. Not every action publishes a floating major; run
the same check against `git/ref/tags/v<major>` before choosing a float.

## Dereference annotated tags before comparing

`.object.sha` on an annotated tag is the tag object, not the commit, so
comparing two tags by it makes identical tags look different. Dereference
when the type is `tag`:

```console
$ gh api \
    --hostname github.com \
    --jq .object.sha \
    repos/<owner>/<action>/git/tags/<tag-object-sha>
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

A major float (`@v6`) moves to the next major float (`@v7`).

An exact patch (`@v4.0.1`) is repinned to the float (`@v4`) when it
exists and resolves to at least that patch. Say `repin X -> Y` in the
subject; "from 4.0.1 to 4" reads as a downgrade otherwise.

A commit SHA with a version comment moves the SHA and the trailing
comment together; a stale `# v8.1.0` beside a v9 SHA is worse than no
comment.

A moving branch (`@main`, `@master`) is left alone and reported as drift;
bump it only when the user names a target.

When upstream has no major tag, pin the exact release and say why in the
commit body, so no one "fixes" it to a float that does not exist.

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
