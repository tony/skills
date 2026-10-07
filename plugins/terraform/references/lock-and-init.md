# Refreshing lock files without wrecking them

Read before running `init` anywhere.

Every command below names `terraform`. Substitute `tofu` when OpenTofu
drives the repository; the subcommands, flags, and lock file format are
the same.

## Contents

- Helper script
- Guard every `init`
- One run per root module
- `-backend=false` removes the credential requirement
- `-upgrade` moves every provider
- Moving one provider, and landing a version the user named
- Selecting a new version narrows the lock to one platform
- When the resolver cannot see the version
- Confirm the lock actually moved
- Verification gates

## Helper script

`lockctl.py` in this plugin's `scripts/` directory does the lock-file work
that must not be retyped: `state` prints one line per provider (source
address, selected version, `h1:` hash count), `drop` removes one provider
block, `stable` filters a version list, `platforms` lists the
`-platform=` values the repository's CI and task files pass to
`providers lock`, and `diff` compares two locks provider by provider.
The commands below name it as `../scripts/lockctl.py`, relative to this
file's directory. Print its absolute path once and write that path
literally in each command, since shell variables do not persist between
Bash calls.

`diff` takes a file or a `<rev>:<path>` git object on each side, run from
the repository root, and prints one line per difference: source, status
(`moved`, `changed`, `count-dropped`, `removed`, `added`), then
`version/h1-count` before and after. It exits 1 when a provider outside
`--allow` changed or disappeared, or any provider's `h1:` count dropped,
and 0 otherwise. `--allow <source>` lets that provider's version move
(repeat it, or pass `'*'` for every provider); a count drop fails
regardless.

## Guard every `init`

`init` writes the lock file, and a lock the run did not start from cannot
be put back. Check each root module before running it.

The lock must be committed. This command fails when it is untracked or
absent:

```console
$ git ls-files \
    --error-unmatch \
    <root-module-dir>/.terraform.lock.hcl
```

The lock must also be unmodified. This command prints nothing when it is:

```console
$ git status \
    --porcelain \
    -- <root-module-dir>/.terraform.lock.hcl
```

A root module that fails either check is skipped and reported, and `init`
does not run there. With no committed lock, `init` writes a new one that
selects the newest version each constraint allows, so even a plain
`init` moves providers. Run it only after the user approves that outcome,
then `git add` the new lock so `git commit -- <paths>` can include it.
With no interactive question tool, skip the module.

After `init`, compare the lock with its committed copy (the `diff` command under
"Moving one provider"). When `init` fails, or `diff` exits non-zero,
restore the committed file and report why:

```console
$ git checkout \
    -- <root-module-dir>/.terraform.lock.hcl
```

A failed `init` leaves the lock edited (a dropped block stays dropped), so
restore on every failure path, offline included.

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
credentials. `-input=false` turns any prompt into an error instead of a
wait ([init options](https://developer.hashicorp.com/terraform/cli/commands/init)).

## `-upgrade` moves every provider

> Upgrade all previously-selected plugins to the newest version that
> complies with the configuration's version constraints. This will
> cause Terraform to ignore any selections recorded in the dependency
> lock file, and to take the newest available version matching the
> configured version constraints.
>
> Source: [terraform init](https://developer.hashicorp.com/terraform/cli/commands/init)

`init` has no per-provider upgrade flag, so `-upgrade` moves every provider
a constraint allows to move. Use it only where that is the goal
(`refresh-lock`):

```console
$ terraform -chdir=<root-module-dir> init -backend=false -upgrade -input=false
```

A constraint left behind (a `~> 6.56.0` in a child module) holds the whole
configuration at `6.56.x`, so land the constraint edit first.

## Moving one provider

Only the target provider's lock block may change. With the guard passed,
remove that block and run plain `init`: Terraform keeps the locked
version of every provider that still has a block and selects the newest
allowed version for the one that does not
([dependency lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock)).

Drop the block for `<provider-source-address>` (the full address as the
lock file spells it, such as `registry.terraform.io/hashicorp/aws`);
the command prints `dropped`, or `absent` when the provider is new in
this directory:

```console
$ python3 ../scripts/lockctl.py drop \
    <root-module-dir>/.terraform.lock.hcl \
    <provider-source-address>
```

Then run the plain `init` command from "One run per root module". The new
block holds hashes for the running platform only; restore the platforms the
old block tracked as the next section describes, naming the provider so no
other block is touched.

Only the target provider's `version`, `constraints`, and `hashes` move.
Check it with `diff`, naming the target in `--allow`:

```console
$ python3 ../scripts/lockctl.py diff \
    --allow <provider-source-address> \
    HEAD:<root-module-dir>/.terraform.lock.hcl \
    <root-module-dir>/.terraform.lock.hcl
```

A non-zero exit lists the other block that changed or the count that
dropped. A CLI bump moves no provider: plain `init`, never `-upgrade`, and
the same command without `--allow` must exit 0.

### Landing a version the user named

Plain `init` selects the newest version the constraint allows, so under a
range (`~> 6.56`) a named `6.57.0` can land as `6.60.2`. When the user named
a version and the constraint admits a newer one, pin it for the refresh:

1. Set the provider's constraint to `= <version>` at every declaring site,
   as a temporary working-tree edit on top of the planned constraints.
2. Drop the block and run plain `init` as above.
3. Put the planned constraints back (`git checkout -- <declaring-file>...`
   when they are committed, a re-edit otherwise), then run `providers lock` naming the
   provider with the platforms the lock tracked (the running platform when
   the count did not drop). Read the lock's `constraints` line back with
   `git diff`: it must show the restored form and the named version. When
   it still shows `= <version>`, restore the lock as in step 4 and stop.
4. Read the version with `lockctl.py state`. If it is not exactly the named
   version, restore the lock from git, put the declaring files back as in
   step 3, report the version that was selected, and stop:

```console
$ git checkout \
    -- <root-module-dir>/.terraform.lock.hcl
```

## Selecting a new version narrows the lock to one platform

`h1:` hashes are per-platform. `terraform init` records them only for the
platform it runs on; teams that need more use
`terraform providers lock -platform=...`
([dependency lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock)).
A provider that moves to a different version comes back tracking only the
platform that ran the bump, and the diff looks like an ordinary version
change. The next `init` on another platform then rewrites
the lock, which fails under `-lockfile=readonly` or any CI step that checks
the tree is clean.

The lock file names no platforms: each provider block holds a flat list of
opaque `h1:` and `zh:` strings. The count of platforms is readable; which
ones is not, and `providers lock -platform=` requires exact names.

Use the count as a tripwire. `lockctl.py diff` compares provider by
provider, so a drop cannot hide behind a provider that tracks more
platforms (a file-wide maximum would). `state` prints the counts
themselves, one line per provider:

```console
$ python3 ../scripts/lockctl.py state \
    <root-module-dir>/.terraform.lock.hcl
```

Output is `<source-address><TAB><version><TAB><h1 count>`. On a lock with
`aws` tracking three platforms and `random` tracking one it prints:

```text
registry.terraform.io/hashicorp/aws	5.60.0	3
registry.terraform.io/hashicorp/random	3.6.0	1
```

If `diff` reports `count-dropped`, find the platform names where the repository writes
them down:

```console
$ python3 ../scripts/lockctl.py platforms
```

It prints each CI or task file (workflows, a Makefile or justfile
target), tracked or not yet added, that runs `providers lock` and the `-platform=` values it names;
documentation that merely mentions the command is not scanned. Where it
prints nothing, ask the user for the names. It reads literal
`-platform=` values only: a loop or variable (`-platform=$p`) prints
nothing. Restore the platforms with
them:

```console
$ terraform -chdir=<root-module-dir> providers lock \
    -platform=linux_amd64 \
    -platform=darwin_arm64 \
    <provider-source-address>
```

Naming the provider restricts the command to it
([providers lock](https://developer.hashicorp.com/terraform/cli/commands/providers/lock));
omit the address only to restore every provider. `providers lock` ignores
`provider_installation` in the CLI configuration, so when the repository
resolves through a mirror, pass the same one with `-fs-mirror=<dir>` or
`-net-mirror=<url>`, as the CI command that locks does (a relative path
resolves from the `-chdir` directory). Never infer the platform
list: a repository that tracked one platform should keep tracking one.
Run `diff` again afterwards; it must exit 0.

Never commit a lock that tracks fewer platforms than it started with
unless the user says yes to that exact file. When the names are unknown,
or the count is still short after `providers lock`, ask. Without an
interactive question tool, or with no answer, restore the committed lock
and leave that root module out of the commit:

```console
$ git checkout \
    -- <root-module-dir>/.terraform.lock.hcl
```

Report it as held back with the before and after counts, and end the run
with the stopped line.

## When the resolver cannot see the version

The registry shows a version the resolver refuses to find. Diagnose the layer:

- A `provider_installation` block in the CLI configuration
  (`.terraformrc`, `terraform.rc`, or wherever `TF_CLI_CONFIG_FILE`
  points) with a `filesystem_mirror` or `network_mirror` that only
  carries what somebody mirrored.
- A plugin cache (`TF_PLUGIN_CACHE_DIR` or `plugin_cache_dir`) that
  already holds an older build of the provider
  ([CLI configuration](https://developer.hashicorp.com/terraform/cli/config/config-file#provider-plugin-cache)).
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
$ python3 ../scripts/lockctl.py state \
    <root-module-dir>/.terraform.lock.hcl
```

Read the file, not `terraform providers`: it prints the configuration's
constraints, which match the target by construction. Report the selected
version per root module, including those that did not move and why.

## Verification gates

`terraform validate` needs an initialised directory, so it runs after `init`,
per root module. `terraform fmt -check -recursive` runs anywhere. Beyond
those, run the checks the repository defines in its `AGENTS.md`,
`CLAUDE.md`, or CI workflow, such as `tflint` or a policy check, never
assumed commands.

A `plan` is not a verification step unless the project asks for it: it needs
backend credentials, reaches live infrastructure, and a non-empty plan is
often pre-existing drift.
