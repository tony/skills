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

## Why this isn't just editing a version string

- **Multiple root modules:** A repo often has multiple root modules, each
  needing its own `init` and `.terraform.lock.hcl`. The plugin identifies them
  by signals (backend/cloud blocks, committed lock files) rather than relying
  on directory conventions.
- **Combined constraints:** Terraform combines constraints from root and child
  modules. Updating partially leads to conflicting versions or initialization
  failures. All declarations must move together.
- **Platform narrowing:** Selecting a new version replaces multi-platform
  coverage with a single platform in the lock file. The plugin preserves
  platform hashes per provider to avoid silent coverage drops.
- **Operator preservation:** Existing operators (e.g., `~>`, `>=`) are
  intentional policies, not drift. The plugin preserves them.
- **CLI pinned externally:** The CLI version is pinned across various
  non-Terraform files (`.terraform-version`, `mise.toml`, CI steps). The
  plugin ensures consistency across all pin sites.
- **Ignored `.terraform/modules/`:** Naive searches edit cached module copies
  that get deleted on the next `init`. The plugin avoids these cached
  directories.
- **OpenTofu `.tofu` files:** OpenTofu prioritizes `.tofu` over `.tf`. The
  plugin respects this precedence.

## Components

| Path | Purpose |
|------|---------|
| `commands/bump-provider.md` | Move one provider across every module that declares it |
| `commands/bump-terraform.md` | Move the CLI version across configuration and non-configuration pin sites |
| `commands/refresh-lock.md` | Re-resolve within existing constraints, every root module |
| `skills/bumping-terraform/SKILL.md` | The shared phase structure, model-invocable without a slash command |
| `references/layout-discovery.md` | Classifying root and child modules by signal, the `.terraform/` cache trap, `.tofu` shadowing, Terragrunt and stacks, and what to ask about |
| `references/pin-sites.md` | Every file a provider or CLI version is pinned in, how constraints combine, operator preservation, and registry lookups |
| `references/lock-and-init.md` | Per-root-module `init`, `-backend=false`, the platform-narrowing trap, blocked resolvers, and verification gates |

## Prerequisites

- `git` and a repository with tracked Terraform or OpenTofu files.
- `terraform` or `tofu` CLI on `PATH`. The plugin resolves versions against
  the detected tool's registry.
- Network access to the provider registry or private registry.
- No cloud credentials required (lock refreshes use `-backend=false`).
- Project quality-check commands (e.g., in `AGENTS.md` / `CLAUDE.md` or CI
  workflow).
