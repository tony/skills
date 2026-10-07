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

- `changelog`: analyze commits, categorize changes, and insert entries into the changelog.
- `refresh`: update the branch's own entries to its current net change; `--commit` stacks a new commit.
- `rewrite-aggressively`: rebase out the branch's earlier changelog commits and regenerate its entries fresh; `--commit` lands one commit.

Choose `refresh` to fix entries by stacking a commit, and
`rewrite-aggressively` to replace the branch's changelog history with one commit.

## Workflow

1. Gather context: read project conventions (`AGENTS.md`, `CLAUDE.md`), find the changelog, and collect commits.
2. Categorize: parse commit types and group related commits.
3. Generate: draft markdown matching the existing changelog style.
4. Review: present proposed entries for approval, each named with the reader question it answers, alongside the commit message they would land under.
5. Insert: apply approved entries to the unreleased section, and commit them when `--commit` was passed or the review step chose to.

With no question tool (Codex, headless runs), a request that asks to add the
entries approves insert only, `--commit` approves insert and commit, and
anything else ends with the proposal and no edit.

## Release Scope

Entries always land in the unreleased section; no version headings, version
files, or tags change unless a release is explicitly requested. The rule is
in `references/branch-scope.md`.

## Supported Changelog Formats

The format is detected from the existing changelog file; see Phase 1 of
`skills/changelog/SKILL.md`.

## Prerequisites

- git: For commit history analysis.
- gh (optional): For PR and label detection.
