# research

Study dependencies locally. Clones upstream repos and creates version-pinned
worktrees matching your project's exact versions.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install research@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add research@skills
```

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Study Dependencies | `/research:deps` | `research:deps` | Clone deps and create version-pinned worktrees in `~/study/` |

## How It Works

1. **Detect tools**: Checks for `rg`, `fd`, `jq`.
2. **Scan manifests**: Finds `package.json`, `pyproject.toml`, `Cargo.toml`, etc.
3. **Filter**: Applies user filter (package, "all", category).
4. **Resolve repos**: Uses metadata, registry, or search.
5. **Confirm**: Presents plan for approval.
6. **Clone**: Clones/fetches to `~/study/<language>/<repo>/`.
7. **Resolve version**: Matches tags or branches (prefers lockfiles).
8. **Create worktree**: Pins to resolved version.
9. **Report**: Summarizes results.

## Supported Manifests

| Manifest | Language | Lockfiles |
|----------|----------|-----------|
| `package.json` | `typescript` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock` |
| `pyproject.toml` | `python` | `uv.lock`, `poetry.lock`, `requirements.txt` |
| `Cargo.toml` | `rust` | `Cargo.lock` |
| `go.mod` | `golang` | `go.sum` |
| `Gemfile` | `ruby` | `Gemfile.lock` |
| `mix.exs` | `elixir` | `mix.lock` |
| `build.gradle` / `build.gradle.kts`| `java` | `gradle.lockfile` |
| `pom.xml` | `java` | — |

## Version Tag Resolution

Prioritizes: exact tags (`5.2.0`), `v`-prefixed, scoped, crate-style, minor
branches, major branches.

## Arguments

| Flag | Effect |
|------|--------|
| `--lang <language>` | Override auto-detected language |
| `--no-worktree` | Clone only, no worktree |

```console
/research:deps vite
```

```console
/research:deps all
```

```console
/research:deps dev
```

```console
/research:deps react --lang typescript
```

```console
/research:deps tokio --no-worktree
```

## Study Directory Layout

Clones structure under `~/study/`:
- **Main Clone**: `~/study/<language>/<repo>/`
- **Pinned Worktree**: `~/study/<language>/<repo>-<version>/`

Monorepos clone once, with worktrees containing all packages.

## Prerequisites

- **git**
- Project with a supported manifest. Manifest detection is automatic.
