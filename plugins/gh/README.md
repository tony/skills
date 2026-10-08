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
Read-only until the final step.

1. Resolves the target repository, including a fork's upstream.
2. Checks the security policy and directs vulnerabilities to private
   reporting.
3. Preflights the repository: issues enabled, templates and forms,
   `CONTRIBUTING.md` requirements.
4. Searches open and closed issues for duplicates.
5. Gathers evidence: records the reproduction (run only after you
   confirm the exact commands), versions, and pinned code, and researches
   upstream projects.
6. Drafts with fixed sections, `###` headings, and `<details>` for long
   output.
7. Strips local paths and PII, then previews through GitHub's renderer.
8. Presents the draft and, on approval, files it with
   `gh issue create --body-file`.

Without an authenticated `gh`, it produces an unverified draft, lists the
checks it could not run, and does not file.

### `rendered-markdown` (skill)

Provides rendering guidance for human-readable markdown. Edit is
disallowed while it runs; Write is used only for a scratch preview file.
- Prevents hard-wrapping in comment bodies.
- Enforces backticks for symbols and one shell command per fence.
- Requires long output in `<details>` and pinned source links.
- Not for filing an issue; use `create-issue`.
- Rules live in `references/rendered-markdown.md` and
  `references/source-links.md`; `references/project-links.md` holds the
  link set for a named upstream project, and `references/pr-and-files.md`
  the pull-request, repository-file, and commit-message rules.

## The wrapping rule exception

GitHub renders newlines as line breaks in comments/issues, but as spaces in
markdown files. Comment bodies avoid hard-wrapping, while repository `.md`
files follow project conventions. The skills respect this boundary rather than
globally reformatting.

## Scope

Use `gh` for filing issues or writing GitHub-rendered markdown (markup and
links). Neither skill drafts a PR description or tightens prose; the
rendering rules, including net-change framing for a pull request, apply
to one written elsewhere.

## Prerequisites

- `gh` 2.43.0 or newer, authenticated with `gh auth login`. Used for
  repository checks, previews, and creating issues. 2.43.0 is the first
  release where `gh release list` accepts `--json`; check with
  `gh --version`.
- `git`, for resolving tags and refs when pinning links.
- `curl` and `jq`, for package-registry lookups and pre-publish link
  checks.
