# terraform

Upgrade Terraform and OpenTofu versions. Discovers every root module, moves
provider constraints together because they combine across modules, and
refreshes lock files.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install terraform@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add terraform@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/terraform:bump-provider <provider> [version]` | `terraform:bump-provider <provider> [version]` | Move a provider across every module that declares it, then refresh the affected lock files |
| `/terraform:bump-terraform [version]` | `terraform:bump-terraform [version]` | Move the CLI version across every module and every pin site outside the configuration |
| `/terraform:refresh-lock` | `terraform:refresh-lock` | Re-resolve providers within the constraints already written, in every root module |

With no version, each bump targets the latest stable release and confirms it
before writing.
- `--audit-only`: Reports the predicted work without writing.
- `--root-module <dir>`: Limits the run to specific root modules.
- `--no-commit`: Leaves the result in the working tree.
- `--no-lock`: Skips the lock refresh.

The `bumping-terraform` skill executes without a slash command when the
request is conversational (e.g., "the providers here are ancient").

## Components

| Path | Purpose |
|------|---------|
| `skills/bump-provider/SKILL.md` | Move one provider across every module that declares it |
| `skills/bump-terraform/SKILL.md` | Move the CLI version across configuration and non-configuration pin sites |
| `skills/refresh-lock/SKILL.md` | Re-resolve within existing constraints, every root module |
| `skills/bumping-terraform/SKILL.md` | The shared phase structure, model-invocable without a slash command |
| `references/layout-discovery.md` | Root and child module classification, the `.terraform/` cache trap, `.tofu` shadowing, Terragrunt and stacks |
| `references/pin-sites.md` | Every file a provider or CLI version is pinned in, operator preservation, registry lookups |
| `references/lock-and-init.md` | Per-root-module `init`, the platform-narrowing trap, blocked resolvers, verification gates |

## Prerequisites

- `git` and a repository with tracked Terraform or OpenTofu files.
- `terraform` or `tofu` CLI on `PATH`. The plugin resolves versions against
  the detected tool's registry.
- Network access to the provider registry or private registry.
- No cloud credentials required (lock refreshes use `-backend=false`).
- Project quality-check commands (e.g., in `AGENTS.md` / `CLAUDE.md` or CI
  workflow).
