# ruff

Upgrade Ruff across repositories. Resolves new rules against each repo's
select list and creates one reviewed commit per rule, citing the upstream
rule doc.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install ruff@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add ruff@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/ruff:bump [version]` | `ruff:bump [version]` | Raise the ruff floor across the repositories in scope and absorb what the release surfaces, one commit per rule |

Defaults to the latest stable release in the current repository, creating
a PR from a throwaway worktree.

**Arguments:**
- `--root <dir>`: Sweep every repository beneath a directory.
- `--repo`: Target specific repositories.
- `--owner <name>`: Filter by account ownership.
- `--audit-only`: Report predicted work without making changes.
- `--adopt-defaults`: Carry through the default-rule-set change.
- `--no-pr`: Commit and push without opening a PR.
- `--no-changelog`: Skip the changelog entry.

## Why this isn't just `ruff check --fix`

- **The headline change is usually not the change that affects you:**
  Explicit `[tool.ruff.lint] select` replaces defaults. The command
  predicts diagnostics per repository.
- **Producing no diagnostics has consequences:** Repositories can
  silently opt out of baseline rules. Widening `select` to whole
  prefixes enables far more than recommended.
- **Formatter scope changes dwarf lint fixes:** Churn from new file
  types in the formatter's scope needs isolated, mechanical commits.
- **The version is often invisible to the resolver:** The command
  diagnoses blocking layers and handles temporary cooldown exemptions
  as revertible commits.
- **Pins drift across files:** It surfaces and resolves disagreements in
  pinned versions (e.g., project metadata vs pre-commit).
- **Not every fix is cosmetic:** Rules altering behavior require tests
  to be re-run, not batched with import reorderings.

## Components

| Path | Purpose |
|------|---------|
| `commands/bump.md` | The command |
| `references/release-triage.md` | Sorting a release, intersecting with configuration, and grading fixes |
| `references/pin-sites-and-gating.md` | Pin sites, diagnosing, and gating resolvers |
| `references/default-rule-set.md` | Measuring default rule set cost and curating adoption |

## Prerequisites

- `git` (with remote push access)
- GitHub CLI, authenticated
- Project's resolver and quality-check commands (defined in `AGENTS.md`/`CLAUDE.md` or CI workflow)
