# gh

File durable GitHub issues with reproductions, pinned links, and stripped PII.
Enforces a markdown writing discipline reusable for any PR, comment, or ticket.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install gh@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add gh@skills
```

The skills below use Claude Code's leading slash. Codex uses the same names
without it (`gh:…`).

## Components

### `/gh:create-issue` (skill)

Files a GitHub issue from existing descriptions, findings, or conversations.
Read-only until the final step.

1. **Resolves repository & checks visibility:** Directs vulnerabilities to
   private reporting paths.
2. **Preflights repository:** Checks for enabled issues, templates, forms, and
   `CONTRIBUTING.md` requirements.
3. **Checks for existing issues:** Searches open and closed issues before
   drafting.
4. **Gathers evidence:** Reproduces defects, records versions, pins code, and
   researches upstream projects.
5. **Drafts:** Enforces fixed sections, `###` headings, `<details>` for long
   output, and nested sections.
6. **Sanitizes and previews:** Strips local paths/PII and validates markup via
   GitHub's renderer.
7. **Files on approval:** Previews title/body and opens via
   `gh issue create --body-file`.

### `rendered-markdown` (skill)

Provides rendering guidance for human-readable markdown. Never edits files.
- Prevents hard-wrapping in comment bodies.
- Enforces backticks for symbols and one shell command per fence.
- Requires long output in `<details>` and pinned source links.
- Rules sync with `references/rendered-markdown.md` and
  `references/source-links.md`.

## The wrapping rule exception

GitHub renders newlines as line breaks in comments/issues, but as spaces in
markdown files. Comment bodies avoid hard-wrapping, while repository `.md`
files follow project conventions. The skills respect this boundary rather than
globally reformatting.

## Plugin comparisons

- **Use `gh`:** For filing issues or writing GitHub-rendered markdown
  (focuses on markup and links).
- **Use `pr`:** For generating, refreshing, or reviewing PR descriptions.
- **Use `lean`:** For tightening prose by removing filler and diff narration
  (focuses on sentences).

## Prerequisites

- **gh** — GitHub CLI, authenticated. Used for repository checks, previews,
  and creating issues.
- **git** — for resolving tags and refs when pinning links.
- **curl** and **jq** — for package-registry lookups and pre-publish link
  checks.
