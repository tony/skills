# Refreshing lock files without wrecking them

Read before running `init` anywhere.

Every command below names `terraform`. Substitute `tofu` when OpenTofu
drives the repository; the subcommands, flags, and lock file format are
the same.

## Contents

- One run per root module
- `-backend=false` removes the credential requirement
- `-upgrade` ignores the lock, by design
- Selecting a new version narrows the lock to one platform
- When the resolver cannot see the version
- Confirm the lock actually moved
- Verification gates

## One run per root module

Each root module owns one `.terraform.lock.hcl`, and `init` only ever
touches the one in the directory it runs in. Four root modules need
four runs. Use `-chdir` rather than a subshell `cd`:

```console
terraform -chdir=<root-module-dir> init -backend=false -upgrade -input=false
```

Child modules have no lock file. Running `init` in one is not an error,
but it produces nothing to commit.

## `-backend=false` removes the credential requirement

Provider installation and lock maintenance do not need the backend.
Passing `-backend=false` skips backend initialisation while still
resolving providers and writing the lock file, so lock refreshes work
against an S3-, GCS-, or HCP-backed configuration with no cloud
credentials present at all.

Use `-input=false` too, so a missing variable fails instead of waiting
on a prompt.

## `-upgrade` ignores the lock, by design

> Upgrade all previously-selected plugins to the newest version that
> complies with the configuration's version constraints. This will
> cause Terraform to ignore any selections recorded in the dependency
> lock file, and to take the newest available version matching the
> configured version constraints.
>
> — [terraform init](https://developer.hashicorp.com/terraform/cli/commands/init)

The constraint edit has to land first: `-upgrade` obeys the constraints.
A `~> 6.56.0` left in any module holds the whole configuration at
`6.56.x`.

## Selecting a new version narrows the lock to one platform

`h1:` hashes are per-platform. `terraform init` records them only for
the platform it runs on, and teams that need more use
`terraform providers lock -platform=...` to pre-populate the set.

Re-running `-upgrade` against an already-selected version preserves the
platforms already recorded. **Selecting a different version does not.**
A lock tracking `linux_amd64` and `darwin_arm64` comes back tracking
only the platform that ran the bump — no warning, no error, and the
diff looks like an ordinary version change.

The `zh:` hashes still cover the official release archives. What is
lost is the multi-platform coverage: the next `init` on another platform
rewrites the lock file, which fails under `-lockfile=readonly` or any CI
step that checks the tree is clean.

The lock file names no platforms: each provider block holds a flat list
of opaque `h1:` and `zh:` strings. How many platforms a provider tracks
is readable; which ones is not, and `providers lock -platform=` requires
exact names.

Use the count as a tripwire. Take the highest `h1:` count of any single
provider before the run, and compare it after:

```console
awk '/^provider /{n=0} /"h1:/{n++; if(n>m) m=n} END{print m+0}' <root-module-dir>/.terraform.lock.hcl
```

Count per provider, not per file: seven providers on one platform and
one provider on seven give the same file total.

If the count dropped, stop and get the platform names from wherever the
repository actually writes them down — a `providers lock` invocation in
CI, a Makefile or justfile target, or the user — then restore them:

```console
terraform -chdir=<root-module-dir> providers lock -platform=linux_amd64 -platform=darwin_arm64
```

Never infer the list. A repository that only ever tracked one platform
should keep tracking one, and guessing a set both drops platforms it had
and adds platforms it never wanted.

## When the resolver cannot see the version

The registry shows a version the resolver refuses to find. Diagnose the
layer first:

- A `provider_installation` block in the CLI configuration —
  `.terraformrc`, `terraform.rc`, or wherever `TF_CLI_CONFIG_FILE`
  points — with a `filesystem_mirror` or `network_mirror` that only
  carries what somebody mirrored.
- `TF_PLUGIN_CACHE_DIR`, which serves a stale copy when the mirror
  cannot be reached.
- A private registry requiring credentials this machine does not have.
- A provider whose new release genuinely has no build for this
  platform.

Report which layer is blocking. Do not edit a mirror configuration to
route around a supply-chain control as a side effect of a version bump.

## Confirm the lock actually moved

The constraint edit and the lock refresh can both succeed while the
selected version stays put: a child module cap, a mirror serving an
older release, a constraint already satisfied. Read the version out of
the lock file and compare it to the target; a zero exit code proves
nothing:

```console
grep -A2 'provider "<provider-source-address>"' <root-module-dir>/.terraform.lock.hcl
```

Read the file, not `terraform providers`. That subcommand prints the
constraints, which match the target by construction, and it needs an
initialised backend that `-backend=false` skipped.

Report the real selected version per root module, including the ones
that did not move and why.

## Verification gates

`terraform validate` requires an initialised directory, so it runs
after `init` and reports per root module. `terraform fmt -check
-recursive` runs anywhere and catches formatting the edits introduced.

Beyond those, run the checks the repository defines in its `AGENTS.md`,
`CLAUDE.md`, or CI workflow, such as a `tflint` pass or a policy check.
Never substitute assumed commands for the ones the project runs.

A `plan` is not a verification step for a version bump unless the
project asks for it: it needs backend credentials, it reaches live
infrastructure, and a non-empty plan is frequently pre-existing drift
rather than anything the bump caused.
