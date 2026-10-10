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

Scope is what the user named: the current repository, each `--repo`, and
the accounts in `--owner`. Under `--root` with no `--owner`, discovery finds
repositories by path only; list each with its remote's owner in the plan and
write to none the user has not approved. A fork flag says nothing about
ownership, since a non-fork can belong to someone else. Forks are out of
scope unless the user names them with `--repo`:

```console
$ gh repo view \
    --json isFork \
    https://github.com/<owner>/<name>
```

Report which repositories were excluded and why.

## Inventory pins from trunk, not the working tree

Pin reads name their repository and host: `git -C <path>` for a clone,
`gh repo view https://github.com/<slug>` and
`gh api --hostname github.com repos/<slug>/...` for the API. The working
directory and inherited `GH_HOST` or `GH_REPO` must not select the target.

`./pins.py` does this deterministically (Python 3.9 or newer). It
resolves the remote (`origin`, else the only remote), requires one declared
HTTPS or SSH URL whose hostname is exactly `github.com`, then fetches and
reads the default branch from the API. Git URL rewrites and SSH configuration
can redirect transport; this check validates the declared URL only.
It prints one JSON object per repository. Print the script's absolute path
once and write it literally in each command:

```console
$ python3 <absolute-path>/pins.py inventory <path-or-slug> [<path-or-slug>...]
```

The JSON lists `pins` from the YAML structure of workflow files, action
metadata files, and every local action a `uses: ./path` names, wherever it
lives in the repository; shell text, comments, and input names such as
`with: {uses: ...}` are not pins. Each pin has `action`, `ref`, `note` (the
trailing comment), and `version` (from the ref, else from the comment; empty
when neither names one). `dependabot` lists the Dependabot configuration
files present on the default branch.

A repository named only by slug (`--repo <owner>/<name>` with no local
clone) is read through the API at one resolved default-branch commit.
Its JSON includes `commit` and the full root `tree` SHA; discovery and content
reads use that snapshot even if the branch moves. A truncated recursive tree
is recovered through complete nonrecursive subtree reads. An incomplete
nonrecursive tree or failed content read stops the inventory.
Without a local clone nothing can be committed: report that repository's
audit and skip its commits, unless the user supplies a checkout path.

Use the helper's JSON filenames as exact values, including embedded whitespace.
It reads NUL-delimited Git paths and JSON API paths, and URL-encodes API lookups.

`"complete": false` means the list is not every pin. `unparsed` names each
file and line the reader could not interpret (anchors, aliases, merge keys,
complex keys, tabs, block-scalar `uses`), and `unresolved` names each local
action that is missing or outside the repository. Report both as they are,
list the pins found as partial, and propose no update for that repository.
If the helper is unavailable or a read fails, report the inventory as
incomplete in the same way.

A pin with an empty `version` (a SHA with no version comment, a branch)
has no known version: report it as unknown and bump it only to a target the
user names. Skip `uses: docker://...` (no tag to verify) and say so. For
`owner/repo/subpath@ref`, look up tags on `owner/repo`. `pins.py` and the
commands here work on github.com only.

## Resolve the latest version

Ask the registry, not memory:

```console
$ gh api \
    --hostname github.com \
    --jq .tag_name \
    repos/<owner>/<action>/releases/latest
```

Some actions publish only tags; when `releases/latest` returns nothing,
list them (see below) and take the highest. `releases/latest` is the most
recently published release, which can be a backport on an older major line;
compare it against the highest major in the tag list before calling it the
target.

## List the majors between the pin and the target

`python3 <absolute-path>/pins.py majors <owner/action> <pin> <target>`
prints the earliest listed tag of each major above the pin and at or below
the target, read from the repository's full tag list (a release list can
omit tag-only majors). Pass the version from the pin's trailing comment, not
the SHA. Exit 4 means a crossed major has no listed tag: the lines printed
are what exists, and stderr names the gap. Report the gap; it is never
evidence that the major changed nothing. By hand, list every tag and take
the lowest `vN.x.y` of each major in range:

```console
$ gh api \
    --hostname github.com \
    --paginate \
    --jq '.[].name' \
    repos/<owner>/<action>/tags
```

For an action pinned at v3 with a v6 target, expect one tag each for v4, v5,
and v6. Link each kept tag only after the release-URL check passes; a tag
with no release object is described as "tag only" and linked as
`https://github.com/<owner>/<action>/tree/<tag>`.

## Verify the target tag exists

Confirm before writing, and gate on exit status
(`python3 <absolute-path>/pins.py tag <owner/action> <tag>` does the same
and exits 1 when the tag is missing, 3 when the lookup failed):

```console
$ gh api \
    --hostname github.com \
    repos/<owner>/<action>/git/ref/tags/<tag> >/dev/null 2>&1
```

A tag is missing only when the lookup returns HTTP 404 and the repository
itself reads (`gh api --hostname github.com repos/<owner>/<action>`), since
GitHub also answers 404 for a private repository this login cannot see. An
auth, rate-limit, or network failure, or a repository that does not read
(`pins.py tag` exit 3), means the tag could not be checked: report that,
never "missing", and do not write the pin.

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

A bump keeps each pin's shape:

- A major float (`@v6`) moves to the next major float (`@v7`).
- An exact tag (`@v4.0.1`) moves to the newest exact tag.
- A commit SHA with a version comment moves the SHA and the trailing
  comment together; a stale `# v8.1.0` beside a v9 SHA is worse than no
  comment.
- A moving branch (`@main`, `@master`) is left alone and reported as drift;
  bump it only when the user names a target.
- When upstream has no major tag, pin the exact release and say why in the
  commit body, so no one "fixes" it to a float that does not exist.

Repinning an exact tag to its float (`@v4.0.1` to `@v4`) collects patches
without a commit per release but gives up reproducibility, since tags can
be moved. It is a pin-policy change, not a bump: list it in the plan as its
own choice, apply it only when approved, and say `repin X -> Y` in the
subject. Only a full commit SHA is immutable; never describe an exact tag
as equivalent to one.

## Check the gates the research surfaces

Before writing a body that claims an upgrade is safe, grep the actual
workflows for each breaking change the release notes name:

- Removed or renamed inputs, and changed defaults.
- `pull_request_target` or `workflow_run` combined with an explicit
  `ref:` or `repository:` pointing at fork data.
- A new runtime requirement. Self-hosted `runs-on` values gate every
  bump to a newer Node runtime.
- Package-manager declaration and lockfile requirements.

State a compatibility conclusion (for example, that the runners meet a new
Node requirement) only from the release note's stated requirement and the
workflows' own `runs-on` values. A requirement the notes do not state, or a
runner the workflows do not name, is reported as unknown.

A fleet-wide fact is not a per-repo fact: where a general claim ("this repo
authenticates via OIDC") does not hold, override the body for that repo.
