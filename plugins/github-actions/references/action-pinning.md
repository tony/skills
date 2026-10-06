# Action pinning and tag verification

Read before writing any version string into a workflow.

## Contents

- Scope
- Inventory pins from trunk, not the working tree
- Resolve the latest version
- Verify the target tag exists
- Dereference annotated tags before comparing
- Choose the pin, preserving the repo's shape
- Check the gates the research surfaces

## Scope

Own repositories only. Check the fork flag, not the owner name:

```console
gh repo view <owner>/<name> --json isFork
```

A fork (`isFork: true`) and an upstream project are out of scope, with
no override: a fork's workflows belong upstream. Report which
repositories were excluded and why.

## Inventory pins from trunk, not the working tree

Read workflow content through `git show <trunk>:<path>`. A checkout
may sit on a feature branch, and auditing that branch reports pins the
default branch does not have.

Cover `.github/workflows/**` and `.github/actions/**` — composite
actions pin versions too, and they are the ones most often missed.

**Word-splitting trap.** In zsh, an unquoted scalar expands as a single
word; in bash it splits on IFS. A loop over a captured file list
therefore works for repos with one workflow file and silently produces
a bogus multi-line ref for repos with two, dropping them from the audit
with no error. The audit then reports the fleet is clean. Always pipe
into `while read -r` instead of iterating an unquoted variable.

## Resolve the latest version

Ask the registry, not memory:

```console
gh api repos/<owner>/<action>/releases/latest --jq .tag_name
```

Some actions publish no releases at all, only tags. Fall back to
listing refs when `releases/latest` returns nothing.

## Verify the target tag exists

A pin naming a tag that does not exist breaks every workflow that
references it. Confirm before writing, and gate on exit status:

```console
gh api repos/<owner>/<action>/git/ref/tags/<tag> >/dev/null 2>&1
```

Piping `gh api` into `jq` or `sed` before checking the status swallows
the 404 and reports a missing tag as present. Check the exit code.

Not every action publishes a floating major. Run the same check against
the major tag (`git/ref/tags/v<major>`) per action before choosing a
float.

## Dereference annotated tags before comparing

`.object.sha` on an annotated tag returns the tag object, not the
commit it points at. Comparing two tags by that field makes identical
tags look different — and can lead to "correcting" research that was
right. Dereference when the type is `tag`:

```console
gh api repos/<owner>/<action>/git/tags/<tag-object-sha> --jq .object.sha
```

This is how to confirm claims like "the floating v6 tag now points at
the v7 commit", which change whether a bump is a behaviour change or a
label correction.

## Choose the pin, preserving the repo's shape

Default to the major-level float: it collects security and bug-fix
patches without a commit per patch release, and keeps dependabot noise
down.

**Currently a major float** (`@v6`) — move to the next major float
(`@v7`).

**Currently an exact patch** (`@v4.0.1`) — repin to the float (`@v4`)
when it exists and resolves to at least that patch. Say `repin X -> Y`
in the subject; "from 4.0.1 to 4" reads as a downgrade otherwise.

**Currently a commit SHA with a version comment** — move the SHA *and*
the trailing comment together. Leaving a stale `# v8.1.0` next to a v9
SHA is worse than no comment.

**No major tag upstream** — pin the exact release and explain why in
the commit body, so a later reader does not "fix" it to a float that
does not exist.

## Check the gates the research surfaces

Before writing a body that claims an upgrade is safe, grep the actual
workflows for each breaking change the release notes name:

- Removed or renamed inputs, and changed defaults.
- `pull_request_target` or `workflow_run` combined with an explicit
  `ref:` or `repository:` pointing at fork data.
- A new runtime requirement. Self-hosted `runs-on` values gate every
  bump to a newer Node runtime.
- Package-manager declaration and lockfile requirements.

A fleet-wide fact is not a per-repo fact. If the body says "this repo
authenticates via OIDC" and one repo uses static keys, that is a false
statement committed permanently to that repo's history. Override the
body wherever the general claim does not hold.
