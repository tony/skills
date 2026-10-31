# Action pinning and tag verification

Read before writing any version string into a workflow.

## Contents

- Scope
- Values that reach a shell
- Inventory pins from trunk, not the working tree
- Resolve the latest version
- List the majors between the pin and the target
- Verify the target tag exists
- Dereference annotated tags before comparing
- Resolve a tag to its commit SHA
- Compare versions with the helper
- Choose the pin, preserving the repo's shape
- Check the gates the research surfaces

## Scope

Scope is what the user named: the current repository, each `--repo`, and
the accounts in `--owner`. This walks a `--root` directory:

```console
$ python3 <absolute-path>/fleet.py discover <root> [--owner <name>]...
```

It prints one JSON object per git repository: `slug`, `owner`, `fork`, `in_scope`, and the `reason` when it
is not. A non-fork can belong to someone else, so under `--root` with no
`--owner` list each in-scope repository with its owner in the plan and write
to none the user has not approved. Forks are out of scope unless the user
names them with `--repo`; a fork status that could not be read counts as
excluded. Report which repositories were excluded and why.

## Values that reach a shell

Action names, refs, tags, file names, and PR titles come from repositories
and upstream maintainers. `pins.py` refuses an action or ref outside plain
`owner/name` and tag characters: it lists the pin under `unsafe`, leaves it
out of `pins`, and marks the inventory incomplete. Write every value taken
from an inventory, tag list, or PR into a command as one single-quoted word,
and write none that the helper has not accepted. A file name is pasted in its
`quoted_files` form from the inventory JSON (shell-quoted by the helper, so a
name holding a quote or `;` is safe); `files` holds the verbatim name for
reading and editing.

## Inventory pins from trunk, not the working tree

Pin reads name their repository and host: `git -C <path>` for a clone,
`gh repo view https://github.com/<slug>` and
`gh api --hostname github.com repos/<slug>/...` for the API. The working
directory and inherited `GH_HOST` or `GH_REPO` must not select the target.

`./pins.py` does this deterministically (Python 3.14 or newer;
running it with no arguments prints every command). It
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
trailing comment), and `version` (from the ref, else from the comment, without
a leading `v`; a prerelease such as `4.0.0-rc.1`, an unprefixed `1.75.0`, and a
`tag=v3.1.0` comment all count; empty when nothing names one). `dependabot` lists the Dependabot configuration
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
file and line the reader could not interpret (custom tags, an alias with
no matching anchor, complex keys, tab indentation, a `uses` that is not one
string), `unresolved` names each local
action that is missing or outside the repository, and `unsafe` names each
pin whose action or ref carries shell syntax. Report all three as they are,
list the pins found as partial, and propose no update for that repository.
If the helper is unavailable or a read fails, report the inventory as
incomplete in the same way.

A pin with an empty `version` (a SHA with no version comment, a branch)
has no known version: report it as unknown and bump it only to a target the
user names. Skip `uses: docker://...` (no tag to verify) and say so. For
`owner/repo/subpath@ref`, look up tags on `owner/repo`. `pins.py` and the
commands here work on github.com only.

## Resolve the latest version

Ask the registry, not memory. This prints the highest stable `vN[.N[.N]]`
tag (or bare `N.N[.N]`) in the full tag list and exits 1 when none is listed.
It compares numbers, so `v10` beats `v9`, and it skips prereleases:

```console
$ python3 <absolute-path>/pins.py latest <owner/action>
```

GitHub's `releases/latest` endpoint returns the most recent non-prerelease,
non-draft release sorted by `created_at`, which is the date of the release's
commit
([docs](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)).
A backport on an older major line can win that sort, and tag-only actions
have no release, so the tag list decides the target. Use a release body only
for its notes.

## List the majors between the pin and the target

The helper prints the earliest listed tag of each major above the pin and at or
below the target, read from the repository's full tag list (a release list can
omit tag-only majors):

```console
$ python3 <absolute-path>/pins.py majors <owner/action> <pin> <target>
```

Pass the pin's `version` from the inventory, with or
without the `v`, never the SHA; a value that is not a version exits 1 with
`not a version`. Exit 4 means a crossed major has no listed tag: the lines printed
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

Confirm before writing, and gate on exit status. The helper exits 1 when the
tag is missing and 3 when the lookup failed:

```console
$ python3 <absolute-path>/pins.py tag <owner/action> <tag>
```

By hand:

```console
$ gh api \
    --hostname github.com \
    repos/<owner>/<action>/git/ref/tags/<tag> >/dev/null 2>&1
```

A tag is missing only when the lookup returns HTTP 404 and the repository
itself reads (`gh api --hostname github.com repos/<owner>/<action>`), since
GitHub answers 404 instead of 403 for a private repository the request cannot
see
([docs](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource)). An
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

A SHA pin needs the commit, not the tag object. The helper prints the commit
SHA, peeling an annotated tag to its commit, with the exit codes of `tag`:
1 when the tag does not exist, 3 when the lookup could not decide. Write
the pin only from a printed SHA; any other outcome stops that action:

```console
$ python3 <absolute-path>/pins.py sha <owner/action> <tag>
```

## Compare versions with the helper

The helper prints `lt`, `eq`, or `gt` over the components both versions
name, with or without a leading `v`, so a float `v6` equals `6.0.1`. A
prerelease sorts below its release (`4.0.0-rc.1` is `lt` `v4`). Use it
wherever one version is "at or above" another; never compare version text by
eye:

```console
$ python3 <absolute-path>/pins.py compare <a> <b>
```

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
