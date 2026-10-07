# Rendered markdown

Contents: The test, Two surfaces, one difference, Symbols, Nothing local, nothing personal, Code blocks, Long output goes in `<details>`, Structure, In a body, mentions are notifications, What to leave out, Preview before publishing, Primary sources.

The writing rules for text a renderer will show a human: issue, pull
request, discussion and review-comment bodies, release notes, tracker
tickets, and a repository's own markdown files.

## The test

Will a maintainer three years from now find this helpful?

They will not have the conversation that produced the text. What
survives is what was written down and what it links to: pin the links,
name the symbols exactly, show the command that was actually run, and
cut sentences that only made sense on the day.

For a pull request, describe the branch's **net** change, not the route
it took; the commits already carry renames, reverted attempts, and
fixups.

## Two surfaces, one difference

In issue, pull request, discussion, and comment bodies GitHub renders
a single newline inside a paragraph as a line break. In a markdown
file it renders as a space.

That decides wrapping. Heading level, table of contents, and mentions
are body-only; everything else applies to both surfaces.

### Comment bodies are never hard-wrapped

Write each paragraph as one long line and separate paragraphs with a
blank line. A body wrapped at 72 or 80 columns renders as ragged short
lines.

### Repository files follow the repository

Match whatever the repository already does; never re-wrap a file because
a body nearby is unwrapped.

### Commit messages wrap

They are not rendered markdown at all. The project's own commit
convention governs.

## Symbols

Wrap every symbol in backticks: function and method names, flags, CLI
subcommands, environment variables, file paths, package names, type
names, config keys, and verbatim error strings. In the title too.

Backticks are also the escape hatch: text inside a code span is never
autolinked, so `` `#123` `` and `` `@import` `` stay literal. An
unescaped `@` in a body has linked to a stranger's GitHub account
before.

## Nothing local, nothing personal

Strip before publishing, every time:

- Absolute local paths. Rewrite `/home/<you>/work/api/src/db.py` as
  `src/db.py`, relative to the repository root.
- Machine names, internal hostnames, LAN addresses, and container ids.
- Email addresses, real names of people who did not consent to be
  named, and account handles used as attribution.
- Tokens, keys, cookies, session ids, and signed URLs — including
  inside pasted logs and stack traces.
- Internal-only URLs a reader outside the org cannot open. Say what
  they contain instead of linking them.

Pasted output is where these leak: read every line of a log before it
goes into a body.

## Code blocks

Use a fenced block for anything a reader would otherwise retype.

- One command per block, so each copies independently.
- No comments inside a fence. Explanation goes above the block as
  ordinary prose.
- A single long command may span lines with a trailing `\`, and a
  multi-statement one-liner may use `\;` — that is still one command.
- Shell commands use `console` with a `$ ` prefix; a multi-line script
  uses `bash` with no prompts. Tag source `python`, `ts`, `rust` when
  highlighting earns it. Plain output and logs may stay untagged.
- To show triple backticks inside a block, fence it with four.

## Long output goes in `<details>`

Logs, stack traces, full diffs, dependency trees, JSON dumps, version
matrices, and anything else a reader scrolls past to reach the point.

```
<details>
<summary>Full stack trace</summary>

...

</details>
```

- The blank line after `</summary>` is required. Without it the body
  is raw HTML and every fence, list, and `**bold**` renders literally.
  This is the single most common way a body ships broken.
- No markdown inside `<summary>` — asterisks and backticks render as
  themselves there. Use `<b>` or `<code>`, or plain text.
- `<details open>` works, and blocks nest, each level needing its own
  blank line after its `</summary>`.
- Indenting a `<details>` four or more spaces past its container's
  content column turns it into a code block. Under a numbered step,
  three spaces is right.

## Structure

### No tables

Rendered tables scroll sideways instead of reflowing, so a narrow
viewport silently hides the right-hand columns. Use nested sections, or a
list with a repeated leading label.

### Start a body's headings at `###`

In an issue the title is a separate field, so a `#` in the body
duplicates it, and `##` draws a full-width horizontal rule. GitHub's own
templates emit `###` per section. A repository file keeps its `#`.

### No table of contents in a body

Headings in an issue body receive no anchor ids, so a `[jump](#repro)`
link is dead. A repository file's headings do get ids, and a table of
contents there resolves.

### Alerts stay at the top level

`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`,
`> [!CAUTION]` — and no others. Inside a `<details>` block or a list
item they degrade silently to a plain blockquote showing the literal
`[!NOTE]`. The marker must sit alone on its blockquote line. One per
body, at most.

## In a body, mentions are notifications

`@person` and `@org/team` send mail. Name someone only when you are
asking them for something.

Every rendered issue reference also writes a backlink onto the target
issue. Citing twenty related issues notifies twenty threads.

Neither fires from a repository file, where `@name` and `#123` are
plain text.

## What to leave out

- Preamble and sign-off. Start at the finding.
- Test counts, file counts, line counts, and "as of" dates.
- Line numbers in prose. Pin a permalink instead.
- Narration of the draft itself — "I have updated the section above".
- `comprehensive`, `robust`, `seamless`, `production-ready`,
  `leverage`, `delve`. Say what the thing does.
- Coded labels (`[R1]`, `Option B`) in text a human reads.
- For a pull request: renames of symbols that never shipped,
  "previously X" framing for behavior no released user saw, and any
  paraphrase of the diff.

## Preview before publishing

GitHub's own renderer will tell you whether the body works. Put the
body inside the quoted heredoc, so no file is needed:

```bash
gh api --method POST /markdown -f mode=gfm -f context=OWNER/REPO -f text="$(cat <<'EOF'
BODY
EOF
)"
```

When the body is already in a file, `-f text="$(cat PATH)"` does the
same. Needs `gh auth login`.

Literal `**` or ``` ``` ``` in that output means a `<details>` block
is missing its blank line. A `<br>` inside a prose paragraph means the
body is hard-wrapped.

Both `mode=gfm` and `context` are required — with the default mode,
`context` is ignored and every reference renders inert, which reads as
a false negative. The preview is also not faithful for label chips,
reference unfurling in lists, team mentions, or cross-repo references,
and it renders with your permissions, so a private reference that
links for you can be inert for everyone else.

## Primary sources

- [Basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
- [Organized with collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)
- [Autolinked references and URLs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls)
- [The GitHub Flavored Markdown spec](https://github.github.com/gfm/)
