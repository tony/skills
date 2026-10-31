# voice

Rephrase any copy for the reader who will use it.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install voice --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install voice@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add voice@skills
```

Claude Code uses a leading slash (`/voice:…`). Codex omits it (`voice:…`).

## Components

### `rephrase`

Runs only when invoked by name. Pass a file path or pasted text, and
optionally the reader or situation:

```text
/voice:rephrase README.md for a first-time user deciding whether to install
```

It fills a reader brief (who the reader is, what they came to do,
where the text renders, when they arrive, and why it matters to them),
then rewrites for that reader. Every claim, command, link, default,
version, requirement, and warning survives; a fact that may not suit
the reader is flagged, never dropped. The reply holds the brief, the
rewrite, and the flagged facts. It edits a file only when you ask.

## References

`references/prose-rules.md` is the house writing rubric every rewrite
follows.
