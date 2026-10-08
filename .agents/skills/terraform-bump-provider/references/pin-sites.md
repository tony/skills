# Every place a version is pinned

Read before writing any version string.

Script paths here (`../scripts/...`) resolve from this file's directory; print the absolute path once and write it literally in each command.

## Contents

- Constraints combine across the whole configuration
- Finding the declarations
- Read the operator before replacing it
- Root modules and reusable modules pin differently
- The CLI version has pin sites outside `.tf` entirely
- Resolve the version and its changelog from the registry
- Upgrade guides on a major jump

## Constraints combine across the whole configuration

> The root module and any child modules can constrain the Terraform
> version and any provider versions the modules use. Terraform
> considers these constraints equal, and only proceeds if all are met.
>
> Source: [Version Constraints](https://developer.hashicorp.com/terraform/language/expressions/version-constraints)

A partial edit is worse than no edit: raise the root module's `aws`
constraint to `~> 6.57.0` while a child module says `~> 6.56.0` and `init`
fails, or, where the constraints overlap, resolves to a version neither file
names. Every declaration of a provider moves in one commit, or none does.

## Finding the declarations

Constraints live in a `terraform` block's `required_providers`, in any `.tf`,
`.tofu`, or `.tf.json` file under any filename. Search for the block, not the filename.

Identity is the source address, not the local name: modules can call one
provider by different local names, and one local name can point at different
sources. Source addresses take the form `[<HOSTNAME>/]<NAMESPACE>/<TYPE>` and
default to `registry.terraform.io`. Resolve a loosely named provider against
the declared addresses, and ask if more than one matches.

## Read the operator before replacing it

The operator in the file encodes an intent. Preserve it, and check
whether the target version requires an edit:

- `~> 6.56.0` allows `6.56.4` but not `6.57.0`. Moving to a new minor
  requires editing the constraint.
- `~> 6.56` allows `6.57.0` but not `7.0.0`. Moving within the major
  requires no edit, but refreshing the lock selects the newest allowed
  release, not necessarily the target. A version the user named lands
  only through the exact-version steps in the lock reference.
- `>= 6.0` or `>= 6.0, < 7.0` already admits the target. Rewriting it
  as `~> 6.57.0` narrows what the module accepts, which is a policy
  change.
- `= 6.56.0` is a deliberate exact pin. Move it exactly.

When the existing constraint is a range or a compound expression, the
new form is a judgment call rather than a substitution. Ask.

**Do not normalise operators repository-wide as a side effect.** A bump
that also converts every `>=` to `~>` is two changes, and the second
one was not requested.

## Root modules and reusable modules pin differently

> A module intended to be used as the root of a configuration [...]
> should also specify the maximum provider version it is intended to
> work with, to avoid accidental upgrades to incompatible new versions.

> Do not use `~>` (or other maximum-version constraints) for modules
> you intend to reuse across many configurations [...] Specify a
> minimum version, document any known incompatibilities, and let the
> root module manage the maximum version.
>
> Source: [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements)

A floor in a reusable module is correct, not drift; a ceiling constrains
every consumer, including ones outside this repository. Leave floors alone
unless the new version is the minimum the module now needs, and say why in
the commit body when you move one.

## The CLI version has pin sites outside `.tf` entirely

`required_version` appears in the `terraform` block of every module
that declares one, root and child alike, and they combine by the same
rule. Beyond those:

- `.terraform-version`: a bare version number, read by tfenv.
- `.tool-versions`: asdf and mise, as a `terraform` or `opentofu` line.
- `mise.toml`, `.mise.toml`, and `.mise/config.toml`: under `[tools]`.
- Workflow files: `hashicorp/setup-terraform` with `terraform_version`,
  `opentofu/setup-opentofu` with `tofu_version`, and any container image
  tag that carries the version in its name.
- `Dockerfile` and `devcontainer.json` image tags, and task-runner
  variables in a `Makefile` or `justfile`.
- Atlantis: `terraform_version` in `atlantis.yaml`, per project or under
  `workflows`.
- pre-commit: a `rev:` under a Terraform hook repository in
  `.pre-commit-config.yaml`; read the file by path, since the name and the
  version sit on different lines.
- Terragrunt: `terraform_version_constraint` in `terragrunt.hcl` or
  `root.hcl`.
- HCP Terraform or Terraform Enterprise: `terraform_version` on a
  `tfe_workspace` resource, which pins the CLI the remote runs use
  ([tfe_workspace](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/workspace)).

Three traps make a search report a clean repository that is not one.

**Match at any depth.** A git pathspec with no leading wildcard anchors to the
repository root, so `Makefile` skips the per-module one beside a root module.
A leading `*` covers both. `just` accepts `justfile`, `Justfile`, and
`.justfile`; `:(icase)` handles the variants.

**Filter on a version, not on the tool's name.** A task runner pins through a
variable named for an abbreviation (`TF_VERSION := 1.11.0`), which a
`terraform|tofu` filter misses, while a filter on the abbreviation alone
matches every `terraform plan` line in a `justfile`. Require the tool name
*and* a version-shaped number on one line.

**Read version files by path.** `.terraform-version` holds a bare version
number, so no name-based filter matches it. Take every line.

`required_version` is declared in `.tf`, `.tofu`, and `.tf.json` files at any depth; list
every declaration with:

```console
$ git grep \
    -n -I -e 'required_version' \
    -- '*.tf' '*.tofu' '*.tf.json'
```

One search covers the first two traps, case-insensitively at any depth:

```console
$ git grep \
    -n -I -i -E \
    -e '(terraform|tofu|tf_?version).*[0-9]+\.[0-9]+' \
    -- ':(icase)*justfile' ':(icase)*makefile' '*Dockerfile*' \
    '*devcontainer.json' '*.tool-versions' '*mise.toml' '*mise/config.toml' \
    '*terragrunt.hcl' '*root.hcl' '*atlantis.yaml' '*.tf.json' \
    '.github/*' '.gitlab-ci.yml' '.gitlab/*' '.circleci/*'
```

Version files take a second search:

```console
$ git grep -n -I -e '' -- '*.terraform-version'
```

These drift apart quietly: the configuration says one version, the version
manager another, CI a third. Inventory all of them, report every
disagreement found before the bump, and move them together.

An exact `required_version` is a hard gate: a module pinned `= 1.14.5`
refuses to initialise under 1.15.8 (`Unsupported Terraform Core version`),
so root modules that disagree about the CLI cannot all run from one machine.

## Resolve the version and its changelog from the registry

Ask the registry, not memory, and confirm the version exists before writing
it anywhere. Every registry implements the protocol's versions endpoint:

```console
$ curl -fsS https://registry.terraform.io/v1/providers/hashicorp/aws/versions \
    | jq -r '.versions[].version'
```

That list holds every release, prereleases included, in no useful order.
Pipe it through `lockctl.py stable` (path rule in the skill) for the newest
stable versions:

```console
$ curl -fsS https://registry.terraform.io/v1/providers/hashicorp/aws/versions \
    | jq -r '.versions[].version' \
    | python3 references/lockctl.py stable 3
```

To confirm a version the user named, test for that exact entry. The command
exits non-zero when it is absent:

```console
$ curl -fsS https://registry.terraform.io/v1/providers/hashicorp/aws/versions \
    | jq -e '.versions[] | select(.version == "6.57.0")'
```

Swap the host for `registry.opentofu.org` when OpenTofu drives the
repository. A source address with a non-default hostname is a private
registry: read `providers.v1` out of
`https://<hostname>/.well-known/terraform.json` and build the path from that
prefix.

`registry.terraform.io` also serves a per-version metadata endpoint with the
release tag, publication date, and the provider's own repository, which makes
a changelog link derivable. Query the target version, never the bare provider
path, which returns the latest release whatever the target is:

```console
$ curl -fsS https://registry.terraform.io/v1/providers/hashicorp/aws/6.57.0 \
    | jq '{version, tag, source, published_at}'
```

That one is an extension, not protocol:

> The public Terraform Registry implements a superset of the API
> described on this page [...] Third-party implementations should not
> include those extensions.
>
> Source: [Provider Registry Protocol](https://developer.hashicorp.com/terraform/internals/provider-registry-protocol)

It returns 404 on `registry.opentofu.org` and on private registries. Where it
is unavailable, confirm the version through the versions endpoint and find the
provider's repository another way before citing a changelog; never construct a
repository URL from the source address.

For the CLI itself, Terraform releases are enumerated at
`https://releases.hashicorp.com/terraform/index.json`. Confirm a named
Terraform version by key; the command exits non-zero when it is absent:

```console
$ curl -fsS https://releases.hashicorp.com/terraform/index.json \
    | jq -e '.versions["1.14.0"]'
```

OpenTofu releases
are tags on its GitHub repository; list the latest stable ones with:

```console
$ git ls-remote --tags --refs https://github.com/opentofu/opentofu.git 'v*' \
    | sed 's#.*refs/tags/v##' \
    | python3 references/lockctl.py stable 3
```

Confirm a named OpenTofu version by its tag; the command exits 2 when the
tag is absent:

```console
$ git ls-remote \
    --exit-code \
    --tags \
    --refs \
    https://github.com/opentofu/opentofu.git \
    refs/tags/v1.10.0
```

Link the CLI changelog at that tag:

- OpenTofu: `https://github.com/opentofu/opentofu/releases/tag/v<version>`.
- Terraform: `https://github.com/hashicorp/terraform/blob/v<version>/CHANGELOG.md`.

For a provider, take `source`, `tag`, and the publication date from the
target version's metadata above and link
`<source>/releases/tag/<tag>`; where the repository keeps a
`CHANGELOG.md`, `<source>/blob/<tag>/CHANGELOG.md` is the alternative. Fetch
the page before linking it.

If the page cannot be fetched, report no changelog link instead of
guessing one, in the report and in the commit body alike. Cite release notes
at the tag the registry reported, not at a branch.

When the user says they confirmed a version themselves, write it, record
"confirmed by you" as how it was confirmed, and treat the changelog link
as unfetched unless a fetch succeeded. Never predict that an unconfirmed
version crosses a major version.

## Upgrade guides on a major jump

- Terraform CLI: `https://developer.hashicorp.com/terraform/language/upgrade-guides`.
- A provider: the registry's guide page for the new major,
  `https://registry.terraform.io/providers/<namespace>/<type>/<version>/docs/guides/version-<major>-upgrade`.
  Not every provider ships one; when the page is missing, say none was
  found.
- OpenTofu: the release notes at the tag.
