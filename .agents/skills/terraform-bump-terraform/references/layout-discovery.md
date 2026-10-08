# Finding the modules, and knowing which kind they are

Read before deciding what is in scope.

## Contents

- Search tracked files only
- Find root modules from the `.tf` files
- Classify by signal, never by name
- Map each child module to the roots that call it
- The lock file belongs to the configuration, not the module
- `.tofu` shadows `.tf`
- JSON syntax is not a text edit
- Other drivers wrap the CLI
- Repositories with no root module
- What to record
- What to ask

Terraform imposes no directory convention, so classify by signal and ask
when the signals do not settle it.

## Search tracked files only

`terraform init` writes a cache to `.terraform/` next to each root
module, and `.terraform/modules/` holds **full copies of every module
source**, `versions.tf` and all. Those copies match every pattern a
real module matches.

They are gitignored, so `rg` skips them, but `find`, `grep -r`, and
`fd -H` do not. `git grep` searches tracked files only and never matches
them, unless run with `--no-index` or `--untracked`. Editing one reports a
bump the next `terraform init` erases.

Scope the search to tracked files:

```console
$ git ls-files -z -- '*.tf' '*.tofu' '*.tf.json'
```

Apply the same exclusion to `.terragrunt-cache/`, and to any vendor
directory the repository keeps.

## Find root modules from the `.tf` files

A lock file may be untracked or gitignored, so a lock listing alone
misses root modules. Start from the configuration. Directories holding a
`backend` or `cloud` block:

```console
$ git grep \
    -l -E \
    -e '^[[:space:]]*(backend[[:space:]]+"|cloud[[:space:]]*\{)' \
    -e '"(backend|cloud)"[[:space:]]*:' \
    -- '*.tf' '*.tofu' '*.tf.json'
```

Lock files that are tracked or untracked-but-not-ignored:

```console
$ git ls-files \
    --cached \
    --others \
    --exclude-standard \
    -- '*.terraform.lock.hcl'
```

Lock files that are gitignored:

```console
$ git ls-files \
    --others \
    --ignored \
    --exclude-standard \
    -- '*.terraform.lock.hcl'
```

Drop paths containing `/.terraform/`: they are module copies, not root
modules.

The union of the directories is the root-module candidate set. Report
"nothing to refresh" only when that set is empty.

## Classify by signal, never by name

`terraform/`, `infra/`, `deploy/`, `live/`, and `environments/` are
conventions somebody made up: a hint for where to look, never the answer.

**Root module**: the directory holds a `backend` or `cloud` block, or
holds a `.terraform.lock.hcl`. These are the directories `terraform
init` runs in, and each one owns exactly one lock file.

**Child module**: the directory is named by a `module` block's
`source` as a local path, or sits under a `modules/` tree, and has
neither a backend nor a lock file. Child modules constrain versions but
own no lock file.

**Neither signal**: a root module on local state with an untracked lock
file looks exactly like a child module nobody calls. Ask rather than guess:
guessing root runs `init` where it does not belong, guessing child leaves a
lock file stale. A directory can be both (a published module with an
`examples/` root), so scope decisions apply per directory.

## Map each child module to the roots that call it

A child module owns no lock file, so a change confined to one is refreshed
through the root modules that call it. List the local-path `module`
sources:

```console
$ git grep \
    -n -E \
    -e '^[[:space:]]*source[[:space:]]*=[[:space:]]*"\.\.?/' \
    -e '"source"[[:space:]]*:[[:space:]]*"\.\.?/' \
    -- '*.tf' '*.tofu' '*.tf.json'
```

Resolve each `source` against the directory of the file that holds it.
A root module is affected when its calls reach the child directly or
through another child module (repeat the resolution until it reaches a
directory with a backend or lock). A child no root module reaches has no
lock to refresh: report it. Remote `source` addresses (registry, `git::`)
do not resolve inside the repository; report them as calling the module
from outside.

## The lock file belongs to the configuration, not the module

> The dependency lock file is a file that belongs to the configuration
> as a whole, rather than to each separate module in the configuration.
>
> Source: [Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock)

Four root modules have four lock files and need four `init` runs; refreshing
one leaves the other three stale.

## `.tofu` shadows `.tf`

OpenTofu reads both extensions, and same-named files do not merge:

> If both `foo.tf` and `foo.tofu` exist in the same directory, OpenTofu
> will only load `foo.tofu` and ignore `foo.tf`.
>
> Source: [OpenTofu Files](https://opentofu.org/docs/language/files/)

A `versions.tf` that OpenTofu never reads changes nothing when edited. When
a directory holds any `.tofu` file, resolve each base name and write to the
file the tool loads.

## JSON syntax is not a text edit

A constraint in `.tf.json` is a string inside nested objects, and
line-oriented HCL edits corrupt it. Parse, modify, and re-serialise, or leave
the file alone and report it.

## Other drivers wrap the CLI

Detect these before planning any `init`, because the wrapper owns the
lifecycle:

- **Terragrunt**: `terragrunt.hcl` or `root.hcl`. Provider blocks are
  frequently produced by `generate` blocks rather than committed as
  `.tf`, so the constraint you need to edit may not exist as a file
  yet. Terragrunt also runs `init` itself with its own caching.
- **Stacks**: `.tfstack.hcl` and `.tfdeploy.hcl`. Components declare
  providers in the stack configuration, and the deployment lifecycle is
  not `terraform init` at all.
- **Workspaces**: several states behind one root module. This changes
  nothing about pins or lock files; note it and move on.

## Repositories with no root module

A published module repository has provider constraints and no lock file.
Constraint bumps apply normally; report that there is nothing to refresh
once the discovery above finds no backend and no lock file.

## What to record

Per directory: kind, lock file presence, how many platforms that lock
tracks per provider, and the providers and `required_version` it
declares. Map each child module to the roots that call it, then ask the
questions below together once the inventory exists.

## What to ask

Ask through `ask-user-choice`, once, with the findings already
gathered, never one directory at a time.

- More than one root module in scope: all of them, a named subset, or
  only the one containing the working directory.
- A directory whose signals do not classify it: root or child.
- Both `terraform` and `tofu` available, or repository signals that
  disagree with the binary on `PATH`: which drives, and therefore which
  registry resolves versions.
- Root modules that disagree about the CLI version: converge them all,
  or move only the selected one and report the rest as drift.

Decide everything else from the signals.

Without an interactive question tool, take the narrower answer to each
(the one root module containing the working directory, the binary on
`PATH`) and say so in the reply.
