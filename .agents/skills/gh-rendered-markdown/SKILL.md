---
name: gh-rendered-markdown
description: >-
  Use when Markdown must render: never hard-wrap issue-body paragraphs; fix
  GitHub code fences, fold logs into details, and pin source links to tags.
allowed-tools: ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"]
metadata:
  source: "plugins/gh/skills/rendered-markdown/SKILL.md"
---

# Rendered markdown

Write the body so it renders, and link it so it still resolves in
three years. Write it per `references/prose-rules.md`.

Two references carry the rules, and the `gh-create-issue` skill follows the same
ones. Read both before drafting:

- `references/rendered-markdown.md` — wrapping, symbols, code
  fences, `<details>`, structure, mentions, what to leave out, and the
  preview command.
- `references/source-links.md` — pinning, autolinking, cross-repo
  references, and the project link set.

## Steps

1. Identify the surface. A comment, issue, or pull request body is
   never hard-wrapped; a repository file follows the repository's own
   wrap convention. Read the project's `AGENTS.md` and `CLAUDE.md`
   when present: a house voice, slop rubric, or wrap convention there
   governs.
2. Draft or fix the text per `rendered-markdown.md`. This skill
   governs what you are writing, not the files around it.
3. Pin and complete every link per `source-links.md`.
4. Preview through GitHub's renderer with the command in
   `rendered-markdown.md`, and read the output before publishing.

## Common mistakes

**Hard-wrapping an issue body at 72 columns.** Correct for a commit
message, wrong here: every newline becomes a line break and the
paragraph renders as ragged stubs.

**Skipping the preview because the draft looks fine.** The source
view does not show a `<details>` block that lost its blank line after
`</summary>`.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
