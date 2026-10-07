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

With no question tool (Codex, headless runs), a request that asks to add the
entries approves insert only, `--commit` approves insert and commit, and
anything else ends with the proposal and no edit. Entries always land in the
unreleased section; see `references/branch-scope.md`.

## Supported Changelog Formats

The format is detected from the existing changelog file; see Phase 1 of
`skills/changelog/SKILL.md`.

## Prerequisites

- git: For commit history analysis.
- python3 (3.9 or newer): For the `rewrite-aggressively` backup and rebase helper.
- gh (optional): For PR and label detection.
