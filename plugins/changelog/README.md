# changelog

Generate and maintain categorized changelog entries from branch commits and
PR context.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install changelog@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add changelog@skills
```

Claude Code uses a leading slash (`/changelog:…`). Codex omits it (`changelog:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/changelog` | `changelog` | Analyze commits, categorize changes, and insert entries into the changelog |
| `/changelog:refresh` | `changelog:refresh` | Update the branch's own entries to its current net change (stacks a new commit with `--commit`) |
| `/changelog:rewrite-aggressively` | `changelog:rewrite-aggressively` | Rebase out the branch's earlier changelog commits and regenerate its entries fresh (commits with `--commit`) |

## Workflow

1. **Gather context**: Detect project info, read conventions (`AGENTS.md`, `CLAUDE.md`), find changelog, and collect commits.
2. **Categorize**: Parse commit types and group related commits.
3. **Generate**: Draft markdown matching the existing changelog style.
4. **Review**: Present proposed entries for approval, each named with the reader question it answers, alongside the commit message they would land under.
5. **Insert**: Apply approved entries to the unreleased section, and commit them when `--commit` was passed or the review step chose to.

With no question tool (Codex, headless runs), a request that asks to add the
entries approves insert only, `--commit` approves insert and commit, and
anything else ends with the proposal and no edit.

## Refresh and Rewrite

Both follow-up commands are hard-scoped to the current branch's net change. They use the PR base (or trunk) and avoid committing by default unless `--commit` is passed.

- **`/changelog:refresh`**: Recomputes entries from the net change and applies the diff in place without rewriting history.
- **`/changelog:rewrite-aggressively`**: Asks approval, backs up the branch, drops pure-changelog commits via non-interactive rebase, then regenerates entries. It never runs `git push`.

## Release Scope

Entries always land in the unreleased section. The plugin does not:
- Create or date version headings.
- Guess release versions or reason about SemVer.
- Edit version files or create tags.

*Cutting a release must be explicitly requested (e.g., "cut v1.53.0").*

## Supported Changelog Formats

The skill detects the format from the existing file. It looks for `CHANGES`,
`CHANGELOG`, `HISTORY`, or `NEWS`, with or without `.md`; for heading styles
such as `## v1.2.3`, `## [1.2.3]`, `## project v1.2.3`, or
`## 1.2.3 (YYYY-MM-DD)`; and for an insertion point at a placeholder comment,
an `## [Unreleased]` heading, or the top of the file.

## Commit Categorization

Section names mirror the existing changelog. Without precedent, `feat` goes
under What's new, `fix` under Bug fixes, `docs` under Documentation, and `test`
under Tests. `chore` and `deps` go under Development only when consumers see
the change, such as a minimum version bump; CI, linter, and dev-tooling changes
are skipped.

Related commits are grouped:

- A TDD sequence (xfail, fix, remove xfail) collapses into one bug fix entry.
- Sequential feature commits on one component merge into one entry.
- Merge commits and formatting-only changes are skipped.

## Project Conventions

The skill reads `AGENTS.md` and `CLAUDE.md` to discover project rules. Priority:
1. **Explicit Rules**: `AGENTS.md` / `CLAUDE.md`.
2. **Implicit Rules**: The existing changelog file (mirrors formatting of the latest release).
3. **Defaults**: Used if no precedent exists.

## Prerequisites

- **git**: For commit history analysis.
- **gh** (optional): For PR and label detection.
