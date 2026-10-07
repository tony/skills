# terraform

Upgrade Terraform and OpenTofu versions. Discovers every root module, moves
provider constraints together because they combine across modules, and
refreshes lock files.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install terraform@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add terraform@skills
```

## When to use it

Use it when one bump must land across several root modules and their
child modules together, or when a lock file must keep the platforms it
already tracks. It is an on-demand run by an agent, not a scheduled
service.

## Skills

Claude Code uses a leading slash (`/terraform:...`). Codex omits it
(`terraform:...`).

Move a provider across every module that declares it, then refresh the
affected lock files:

```text
/terraform:bump-provider <provider> [version]
```

Move the CLI version across every module and every pin site outside the
configuration:

```text
/terraform:bump-terraform [version]
```

Re-resolve providers within the constraints already written, in every root
module:

```text
/terraform:refresh-lock
```

With no version, each bump targets the latest stable release and confirms it
before writing.

- `--audit-only`: Reports the predicted work without writing.
- `--root-module <dir>`: Limits the run to specific root modules.
- `--no-commit`: Leaves the result in the working tree.
- `--no-lock`: Skips the lock refresh (`bump-provider` and `bump-terraform`).

Terragrunt and Terraform stacks are detected and reported, not driven.

The `bumping-terraform` skill executes without a slash command when the
request is conversational (e.g., "the providers here are ancient").

## Components

- `skills/bump-provider/SKILL.md`: move one provider across every module that declares it.
- `skills/bump-terraform/SKILL.md`: move the CLI version across configuration and non-configuration pin sites.
- `skills/refresh-lock/SKILL.md`: re-resolve within existing constraints, every root module.
- `skills/bumping-terraform/SKILL.md`: routes a conversational request to one of the three skills above and holds the conventions they share.
- `references/layout-discovery.md`: root and child module classification, child-to-root mapping, the `.terraform/` cache trap, `.tofu` shadowing, Terragrunt and stacks.
- `references/pin-sites.md`: every file a provider or CLI version is pinned in, operator preservation, registry lookups.
- `references/lock-and-init.md`: per-root-module `init` and its guard, the platform-narrowing trap, blocked resolvers, verification gates.
- `scripts/lockctl.py`: per-provider lock state, single-block removal, stable-version filter, platform names from CI and task files that run `providers lock`, and a provider-by-provider lock comparison that exits non-zero on an unexpected change or a platform-count drop.

## Prerequisites

- `git` and a repository with tracked Terraform or OpenTofu files.
- `python3` (3.9 or newer) for `scripts/lockctl.py`.
- `curl` and `jq` for registry and release lookups.
- `terraform` or `tofu` CLI on `PATH`. The plugin resolves versions against
  the detected tool's registry.
- Network access to the provider registry or private registry.
- No backend credentials required (lock refreshes use `-backend=false`).
  A private registry or private module source needs its own credentials.
- Project quality-check commands (e.g., in `AGENTS.md` / `CLAUDE.md` or CI
  workflow).
