<!-- portable: verbatim-fences -->

# 2026-08-12 — One project, three spellings

The spread gate asks whether a pattern crosses more than one project.
The same project answers to three different strings depending on which
channel names it, so unioning the channels counts it more than once and
a single project's quirk clears the gate.

Paths below are redacted to `<user>`; the shapes are what matter.

## Input

The raw prompt-history file names the project as an absolute path:

```console
jq -r 'select(.project != null) | .project' ~/.claude/history.jsonl | sort -u
```

```
/home/<user>/work/ai/skills
```

`agentgrep` normalizes that same record to a tilde form with a trailing
slash:

```console
uvx agentgrep --color never search 'self-improvement' --limit 6 --no-progress --json | jq -r '.results[] | select(.store=="claude.history") | .metadata.project'
```

```
~/work/ai/skills/
```

Transcripts carry no project field at all; the project is a mangled
path segment:

```console
ls -d ~/.claude/projects/*ai-skills*
```

```
-home-<user>-work-ai-skills
-home-<user>-work-ai-skills-private
```

## Reasoning

Three strings, one project: `/home/<user>/work/ai/skills`,
`~/work/ai/skills/`, and `-home-<user>-work-ai-skills`.

The documented spread query takes `.metadata.project` for prompt
records and the `/projects/<slug>` capture for transcript records, then
pipes the union to `sort -u | wc -l`. A pattern occurring in exactly
one project, seen in both channels, comes back as 2 — enough to clear
"across more than one project" on evidence from a single project.

The failure runs one way only. Spread is never undercounted by this;
it is inflated, and inflated spread promotes findings that the bar
exists to reject.

The last line is a second trap. `-home-<user>-work-ai-skills-private`
is a different project whose slug extends the first one's, so matching
by prefix merges two projects into one and undercounts spread — the
opposite error, from the same ambiguity.

## Output

Normalize before counting. Reduce every attribution to one canonical
form — strip a trailing slash, expand or contract the home prefix
consistently, and translate the slug's dashes back to separators —
then deduplicate.

Compare slugs for equality, never by prefix.

Codex and Grok prompt histories carry no project field in any form, so
their spread is not countable from a result at all. Say so rather than
scoring it zero, and rather than quietly letting the countable channels
stand in for the whole corpus.
