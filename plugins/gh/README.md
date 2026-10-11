# gh

File durable GitHub issues with reproductions, pinned links, and stripped PII.
Enforces a markdown writing discipline reusable for any PR, comment, or ticket.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install gh --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install gh@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add gh@skills
```

Claude Code uses a leading slash (`/gh:…`). Codex omits it (`gh:…`).

## Components

### `/gh:create-issue` (skill)

Files a GitHub issue from existing descriptions, findings, or conversations.
Changes nothing on GitHub until you approve filing; it writes only a
local scratch file and runs a reproduction only after you confirm it.

It resolves the target repository (stopping rather than guessing when a
headless run finds several remotes), checks the security policy and
templates, searches for duplicates, gathers a reproduction and pinned
links, scans the draft for local paths and PII, previews it through
GitHub's renderer, and files with `gh issue create --body-file` only
after approval. Deterministic steps live in `scripts/issue.py`.

Without an authenticated `gh`, it produces an unverified draft, lists the
checks it could not run, and does not file.

### `rendered-markdown` (skill)

Rewrites a pull-request description, comment, or issue body so it renders
and its links resolve, and scans and lints it first. Edit is disallowed
while it runs; Write is used only for a scratch file. Rules live in
`references/rendered-markdown.md`, `references/source-links.md`, and
`references/source-pins.md`; `references/project-links.md` holds the link
set for a named upstream project.

## Scope

Pull-request and repository-file rules are in
`references/pr-and-files.md`.

## Prerequisites

- `gh` 2.43.0 or newer, authenticated with `gh auth login`. The floor is
  the first release with `gh release list --json`
  ([v2.43.0 notes](https://github.com/cli/cli/releases/tag/v2.43.0)); an
  older `gh` shows up at run time as the `Unknown JSON field` probe in
  `create-issue`.
- `python3` 3.9 or newer, for `scripts/issue.py` (standard library only).
- `git`, for resolving tags and refs when pinning links.
- `curl` and `jq`, for package-registry lookups and pre-publish link
  checks.
