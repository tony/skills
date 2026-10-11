---
name: gh-rendered-markdown
description: >-
  Use when a GitHub PR description, comment, or issue body looks broken:
  wrapped lines, bad code fences, long logs, links. Not for filing an issue.
allowed-tools: ["Read", "Write", "Bash"]
metadata:
  source: "plugins/gh/skills/rendered-markdown/SKILL.md"
---

# Rendered markdown

Write the body so it renders, and link it so it still resolves in
three years. Write it per `references/prose-rules.md`.

Read `references/rendered-markdown.md` before drafting. When the text
has links, also read `references/source-links.md` and
`references/source-pins.md`; when it names an upstream open-source
project, `references/project-links.md`. For a pull-request
description or a repository markdown file, also read
`references/pr-and-files.md`.

## Steps

1. Identify the surface (comment, issue, or pull-request body; repository
   file). Read the project's `AGENTS.md` and `CLAUDE.md` when present: a
   house voice, slop rubric, or table rule there overrides these
   references (not link pinning or the sanitize step). A wrap convention
   applies only to repository files (see `pr-and-files.md`).
2. Get the text. The script is `references/issue.py`; it resolves from
   this skill's directory to an absolute path written literally in each
   command, and `scan` and `lint` are documented in its docstring (its
   other subcommands serve `create-issue`). When the text is already on
   GitHub, fetch it from its issue, pull-request, or comment URL; writing
   the fixed text back is the user's call:

   ```console
   $ python3 /absolute/path/to/scripts/issue.py fetch URL
   ```

3. Draft or fix the text per `rendered-markdown.md`; pin and complete
   every link per the link references.
4. Run "Preview before publishing" in `rendered-markdown.md` with that
   script. Without a shell, reread by eye. A `0 length` row means trim the
   excerpt and link the full log (Length in that reference). Leave a table
   in someone else's body alone.

## Reply

A status line (repository, and whether the preview ran), the rewritten body
fenced with four backticks, then one sentence naming what the user must do
before posting. No bullet list, command, or explanation of what changed.

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

Before posting, replace `<SHA>` with the commit where you saw the bug, or a release tag.
`````

If the text cannot be fixed (no body was given, or the surface is a
commit message), reply with one sentence saying so and what the user
should send.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
