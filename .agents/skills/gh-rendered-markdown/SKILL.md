---
name: gh-rendered-markdown
description: >-
  Use when GitHub Markdown must render: no hard-wrapped bodies, fix code
  fences, fold logs into details, pin links. Not for filing an issue.
allowed-tools: ["Read", "Grep", "Glob", "Bash"]
metadata:
  source: "plugins/gh/skills/rendered-markdown/SKILL.md"
---

# Rendered markdown

Write the body so it renders, and link it so it still resolves in
three years. Write it per `references/prose-rules.md`.

Two references carry the rules, and `create-issue` follows the same
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
   governs what you are writing, not the files around it. Filing an
   issue belongs to `create-issue`, which applies these rules.
3. Pin and complete every link per `source-links.md`.
4. Preview through GitHub's renderer with the stdin form in
   `rendered-markdown.md`: the body goes inside a quoted heredoc in
   the command, so no file is written. Read the output before
   publishing. When `gh` is unauthenticated or offline, say the
   preview did not run.

## Reply

The rewritten body comes first. Add only what the user must do before
posting, such as replacing a `<SHA>` placeholder or an unrun preview.
Do not narrate what changed or why GitHub renders it that way.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

`````text
Rewritten body for example/widgets, preview not run (gh is not logged in).

````markdown
The retry loop drops the timeout on the third attempt.

<details>
<summary>Full stack trace</summary>

```
TypeError: Cannot read properties of undefined (reading 'target')
```

</details>

See [`src/build.js`](https://github.com/example/widgets/blob/<SHA>/src/build.js#L38-L50).
````

Before posting:

- Replace `<SHA>` with the commit where you saw the bug, or a release tag.
`````

If the text cannot be fixed (no body was given, or the surface is a
commit message), reply with one sentence saying so and what the user
should send.

## Common mistakes

**Hard-wrapping an issue body at 72 columns.** Correct for a commit
message, wrong here: every newline becomes a line break and the
paragraph renders as ragged stubs.

**Skipping the preview because the draft looks fine.** The source
view does not show a `<details>` block that lost its blank line after
`</summary>`.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
