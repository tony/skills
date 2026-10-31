# voice

Write or rephrase copy for the reader who will use it.

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

### `phrase`

Runs when you ask to write or rephrase copy for its audience, or by
name. To rephrase, pass a file path or pasted text, and optionally the
reader or situation:

```text
/voice:phrase README.md for a first-time user deciding whether to install
```

For new copy, pass notes, facts, or code, and the path it is for:

```text
/voice:phrase the install section of docs/quickstart.md for a first-time user, from these notes: ...
```

It fills a reader brief (who the reader is, what they came to do,
where the text renders, when they arrive, and why it matters to them),
then writes for that reader. A rephrase keeps every claim, command,
link, default, version, requirement, and warning. New copy claims only
what the notes or the files it reads support. A fact that may not suit
the reader, or a gap the notes leave, is flagged, never dropped or
guessed. The reply holds the brief, the copy, and the flagged items. It
writes a file only when you ask.

## References

`references/prose-rules.md` is the house writing rubric every rewrite
follows.
