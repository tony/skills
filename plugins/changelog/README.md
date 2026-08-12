# changelog

Generate and maintain categorized changelog entries from branch commits and
PR context.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install changelog@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add changelog@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/changelog` | `changelog` | Analyze commits, categorize changes, and insert entries into the changelog |
| `/changelog:refresh` | `changelog:refresh` | Update the branch's own entries to its current net change (stacks a new commit with `--commit`) |
| `/changelog:rewrite-aggressively` | `changelog:rewrite-aggressively` | Rebase out the branch's earlier changelog commits and regenerate its entries fresh (commits with `--commit`) |

## Workflow

1. **Gather context**: Detect project info, read conventions (`AGENTS.md`), find changelog, and collect commits.
2. **Categorize**: Parse commit types and group related commits.
3. **Generate**: Draft markdown matching the existing changelog style.
4. **Review**: Present proposed entries for approval, each named with the reader question it answers, alongside the commit message they would land under.
5. **Insert**: Apply approved entries to the unreleased section, and commit them when the review step chose to.

## Refresh and Rewrite

Both follow-up commands are hard-scoped to the current branch's net change. They use the PR base (or trunk) and avoid committing by default unless `--commit` is passed.

- **`/changelog:refresh`**: Recomputes entries from the net change and applies the diff in place without rewriting history.
- **`/changelog:rewrite-aggressively`**: Rebuilds history by dropping pure-changelog commits via non-interactive rebase, then regenerates entries. (Does not run `git push`).

## Release Scope

Entries always land in the unreleased section. The plugin does not:
- Create or date version headings.
- Guess release versions or reason about SemVer.
- Edit version files or create tags.

*Cutting a release must be explicitly requested (e.g., "cut v1.53.0").*

## Supported Changelog Formats

The command auto-detects the changelog format from the existing file:

| File names | `CHANGES`, `CHANGES.md`, `CHANGELOG`, `CHANGELOG.md`, `HISTORY.md`, `NEWS.md` |
|------------|--------------------------------------------------------------------------------|
| Heading styles | `## v1.2.3`, `## [1.2.3]`, `## project v1.2.3`, `## 1.2.3 (YYYY-MM-DD)` |
| Insertion points | Placeholder comments, `## [Unreleased]` headings, top of file |

## Commit Categorization

Commits are mapped to changelog sections based on their type prefix. **Section names mirror the existing CHANGES file when one exists** — the table below lists fallback names used only when the file has no precedent:

| Commit type | Fallback section |
|-------------|------------------|
| `feat` | What's new (or `Features`, if the project uses that) |
| `fix` | Bug fixes |
| `docs` | Documentation |
| `test` | Tests |
| `chore`, `deps` | Development |

Related commits are grouped automatically:
- TDD sequences (xfail → fix → remove xfail) collapse into a single bug fix entry
- Sequential feature commits on the same component merge into one entry
- Merge commits and formatting-only changes are skipped

## Project Conventions

The command reads `AGENTS.md` and `CLAUDE.md` to discover project rules. Priority:
1. **Explicit Rules**: `AGENTS.md` / `CLAUDE.md`.
2. **Implicit Rules**: The existing changelog file (mirrors formatting of the latest release).
3. **Defaults**: Used if no precedent exists.

Follows project-specific commit formats prescribed in conventions.

## Prerequisites

- **git**: For commit history analysis.
- **gh** (optional): For PR and label detection.

## Language-Agnostic Design

Detects project details across ecosystems (`pyproject.toml`, `package.json`, etc.) and seamlessly adapts to existing changelog formats.
