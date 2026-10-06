# Refreshing lock files without wrecking them

Read before running `init` anywhere.

Every command below names `terraform`. Substitute `tofu` when OpenTofu
drives the repository; the subcommands, flags, and lock file format are
the same.

## Contents

- One run per root module
- `-backend=false` removes the credential requirement
- `-upgrade` moves every provider
- Moving one provider
- Selecting a new version narrows the lock to one platform
- When the resolver cannot see the version
- Confirm the lock actually moved
- Verification gates

## One run per root module

Each root module owns one `.terraform.lock.hcl`, and `init` touches only
the one in the directory it runs in, so four root modules need four runs.
Use `-chdir` rather than a subshell `cd`. This form keeps every locked
version and installs what the lock names:

```console
$ terraform -chdir=<root-module-dir> init -backend=false -input=false
```

Child modules have no lock file; `init` in one produces nothing to commit.

## `-backend=false` removes the credential requirement

Provider installation and lock maintenance do not need the backend.
`-backend=false` skips backend initialisation while still resolving
providers and writing the lock file, so refreshes work with no cloud
credentials. Pass `-input=false` too, so a missing variable fails instead
of prompting.

## `-upgrade` moves every provider

> Upgrade all previously-selected plugins to the newest version that
> complies with the configuration's version constraints. This will
> cause Terraform to ignore any selections recorded in the dependency
> lock file, and to take the newest available version matching the
> configured version constraints.
>
> — [terraform init](https://developer.hashicorp.com/terraform/cli/commands/init)

`init` has no per-provider upgrade flag, so `-upgrade` moves every provider
a constraint allows to move. Use it only where that is the goal
(`refresh-lock`):

```console
$ terraform -chdir=<root-module-dir> init -backend=false -upgrade -input=false
```

A constraint left behind (a `~> 6.56.0` in a child module) holds the whole
configuration at `6.56.x`, so land the constraint edit first.

## Moving one provider

Only the target provider's lock block may change. Remove that block and run
plain `init`: Terraform keeps the locked version of every provider that
still has a block and selects the newest allowed version for the one that
does not.

Drop the block for `<provider-source-address>` (the full address as the
lock file spells it, such as `registry.terraform.io/hashicorp/aws`):

```console
$ awk -v src='<provider-source-address>' '$0 ~ "^provider \"" src "\" \\{" {skip=1} !skip{print} skip && /^}/{skip=0}' <root-module-dir>/.terraform.lock.hcl > <root-module-dir>/.terraform.lock.hcl.new && mv <root-module-dir>/.terraform.lock.hcl.new <root-module-dir>/.terraform.lock.hcl
```

Then run the plain `init` command from "One run per root module". The new
block holds hashes for the running platform only; restore the platforms the
old block tracked as the next section describes, naming the provider so no
other block is touched.

Only the target provider's `version`, `constraints`, and `hashes` move.
Confirm with `git diff` on the lock file and report any other block that
changed. A directory with no lock block for the provider (it is new there)
needs no removal. A CLI bump moves no provider: plain `init`, never
`-upgrade`.

## Selecting a new version narrows the lock to one platform

`h1:` hashes are per-platform. `terraform init` records them only for the
platform it runs on; teams that need more use
`terraform providers lock -platform=...`.

Re-running `-upgrade` against an already-selected version preserves the
recorded platforms. **Selecting a different version does not.** A lock
tracking `linux_amd64` and `darwin_arm64` comes back tracking only the
platform that ran the bump, with no warning, and the diff looks like an
ordinary version change. The next `init` on another platform then rewrites
the lock, which fails under `-lockfile=readonly` or any CI step that checks
the tree is clean.

The lock file names no platforms: each provider block holds a flat list of
opaque `h1:` and `zh:` strings. The count of platforms is readable; which
ones is not, and `providers lock -platform=` requires exact names.

Use the count as a tripwire. Print one line per provider before the run and
again after, and compare provider by provider; a file-wide maximum would let
a drop hide behind a provider that tracks more platforms:

```console
$ awk '/^provider "/{p=$2; gsub(/"/,"",p); o[++k]=p} /^[[:space:]]*"h1:/{c[p]++} END{for(i=1;i<=k;i++) printf "%s\t%d\n", o[i], c[o[i]]+0}' <root-module-dir>/.terraform.lock.hcl
```

Output is `<source-address><TAB><h1 count>`. On a lock with `aws`
tracking three platforms and `random` tracking one it prints:

```text
registry.terraform.io/hashicorp/aws	3
registry.terraform.io/hashicorp/random	1
```

If the count dropped, stop and get the platform names from where the
repository writes them down (a `providers lock` invocation in CI, a
Makefile or justfile target) or from the user, then restore them:

```console
$ terraform -chdir=<root-module-dir> providers lock -platform=linux_amd64 -platform=darwin_arm64 <provider-source-address>
```

Naming the provider restricts the command to it
([providers lock](https://developer.hashicorp.com/terraform/cli/commands/providers/lock));
omit the address only to restore every provider. Never infer the platform
list: a repository that tracked one platform should keep tracking one.

## When the resolver cannot see the version

The registry shows a version the resolver refuses to find. Diagnose the layer:

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

The constraint edit and the lock refresh can both succeed while the selected
version stays put (a child module cap, a mirror serving an older release).
Read the version out of the lock file and compare it to the target; a zero
exit code proves nothing:

```console
$ grep -A2 'provider "<provider-source-address>"' <root-module-dir>/.terraform.lock.hcl
```

Read the file, not `terraform providers`: it prints constraints, which match
the target by construction, and needs a backend `-backend=false` skipped.
Report the selected version per root module, including those that did not
move and why.

## Verification gates

`terraform validate` needs an initialised directory, so it runs after `init`,
per root module. `terraform fmt -check -recursive` runs anywhere. Beyond
those, run the checks the repository defines in its `AGENTS.md`,
`CLAUDE.md`, or CI workflow, such as `tflint` or a policy check, never
assumed commands.

A `plan` is not a verification step unless the project asks for it: it needs
backend credentials, reaches live infrastructure, and a non-empty plan is
often pre-existing drift.
