# Detecting Skill Usage From Local Agent History

Prompts you typed and transcripts your agents wrote sit in local stores on
your disk. This file turns them into a per-skill invocation count and lists
the ways that count comes back confidently wrong. `../scripts/sweep.py counts`
does the counting; this file covers getting its inputs and reading its output.

Contents:

- Invocations land in two places
- Run the counter
- Renames split the history
- Supersessions split it the other way
- Spread, not just repetition
- Cost
- Other hosts and other search tools
- Redact before anything ships

## Invocations land in two places

A skill is invoked by typing its slash name or by the model calling the
skill tool. Each way is recorded somewhere else, and a count from one
channel alone is wrong.

**Typed slash commands** live in the host's prompt history. For Claude Code
that is `~/.claude/history.jsonl`: one JSON object per line with `display`,
`project`, and `timestamp` in epoch milliseconds. The counter reads it
directly and matches only prompts that start with `/plugin:skill`, so a
prompt that merely mentions one does not score. It misses bare `/skill`
names of user-level skills; say so in the report.

**Skill-tool invocations** write a `Launching skill: <plugin>:<skill>` line
into the conversation transcript, not into prompt history. Collect one line
per occurrence into a scratch file. Prefer the host's own session-search
tool. Without one, Claude Code transcripts are searchable with `rg`:

```console
$ rg \
    --only-matching \
    --no-filename \
    --no-line-number \
    --glob '*.jsonl' \
    'Launching skill: [a-z0-9:-]+' \
    ~/.claude/projects
```

Redirect the output to a file in the scratch directory. Confirm the line
form with one search before counting; an empty file means this host does
not write that line, and the tool channel is unavailable, not zero.

The tool channel has no usable date, so the era split comes from the slash
channel alone and a skill the model reaches for on its own is undercounted
there. A skill is unused only when it is absent from both channels.
Reporting from the tool channel alone recommends deleting heavily used
skills; reporting from the slash channel alone erases the ones the model
invokes unprompted.

Do not predict a skill's channel from its frontmatter:
`disable-model-invocation: true` does not confine a skill to the slash
channel.

## Run the counter

Create the scratch directory outside the repository, because a sweep that
leaves untracked files in the tree it measures has edited it. Print the
path and use that literal path in every later command.

```console
$ mktemp -d "${TMPDIR:-/tmp}/sweep.XXXXXX"
```

Write the current skill names, one per line, to `catalog.txt` there, then
count:

```console
$ python3 ../scripts/sweep.py counts \
    --history ~/.claude/history.jsonl \
    --boundary <era boundary> \
    --tool-log <scratch>/tool-log.txt \
    --catalog <scratch>/catalog.txt \
    --alias <old-name>=<current-name>
```

Pass one `--alias` per rename. The output is JSON: per skill `slash_all`,
`slash_era`, `tool_all`, `all_time`, `projects_all`, `projects_era`, plus
`rank_all`, `rank_era`, and per-channel `status`. Use `rank_all` for the
all-time ranking and `rank_era` for the current-era ranking; the second is
slash-only, so say so.

`complete` is `false` unless the history parsed without malformed lines and
the tool log held at least one launch. Apply no threshold to an incomplete
count. A zero from an incomplete channel is not an absence. An archived or
reclaimed transcript store comes back clean, complete, and wrong, so state
what the count assumes about the corpus.

## Renames split the history

A renamed skill keeps its old invocations under the old name. Counting only
the current name undercounts, sometimes by most of the total.

```console
$ git log \
    --diff-filter=R \
    --name-status \
    --format='%h %s' \
    -- 'plugins/*/skills/*'
```

Read commit subjects for renames the detector scored below its threshold.
Sum across every name one skill has had, via `--alias`, and across nothing
else; a replacement is not a rename.

## Supersessions split it the other way

A rename you detect and sum across. A supersession, a skill replaced by a
different one or a set, leaves no git trace linking the two, and summing
them is wrong: the predecessor's invocations all belong to the era before
the successor shipped.

A superseded skill has a full all-time record and an empty recent half; its
successor shows the mirror image, empty until its birth date and holding
the traffic after. A predecessor that went quiet with no sibling picking up
its work is abandoned, which is a different finding with a different remedy.

Window each finding against the birth date of the skill that covers it. A
procedure typed by hand is a discoverability gap only if the typing
continued after the skill existed.

## Spread, not just repetition

A pattern confined to one project is that project's quirk. In the slash
channel the counter reports distinct projects per skill from the record's
top-level `project`. For a pattern, count distinct `project` values over the
prompts in its cluster by equality, not by prefix: one path can extend
another.

Transcript results carry the project in the `/projects/<slug>` path
segment. Some hosts' histories carry no project at all; report their spread
as not countable instead of scoring it zero.

## Cost

An exhaustive transcript search reads every store on disk. Run it once,
save the raw output, and re-slice it locally rather than running one
search per skill. The slash channel is a single file read and finishes in
seconds. Say before starting which of the two you are running.

## Other hosts and other search tools

The slash extraction is a Claude Code shape. Other hosts record the same
intent differently, so extract per host. When a host's channel comes back
near-empty, treat it as "the extraction does not fit this host" until
proven otherwise, not as "this host does not use skills".

`agentgrep` searches the stores of several hosts at once and is an
optional alternative to the host's search tool. It runs through `uvx`, so
`uv` must be installed. Before relying on it:

```console
$ uvx agentgrep search --help
```

Use only the flags that help lists. If `uv` or the tool is missing, the
command fails, or a flag the query needs is absent, stop using it: fall back
to the host's search tool or the `rg` command above, and report the other
hosts' stores as not searched.

Whatever the tool, confirm the run completed before drawing conclusions.
A bounded or partial result looks identical to a genuine absence. Read the
tool's own completeness indicator, and threshold on the raw match count it
reports, not on a count taken after deduplication or after the result
limit. If the tool exposes no such indicator, mark that channel unverified
in the report.

## Redact before anything ships

Corpus results carry absolute paths, project slugs derived from them, and
prompts quoting local paths, hostnames, and client or employer names. The
ledger may hold them because it lives outside the working tree. A
`SKILL.md`, commit message, pull request body, or issue may not. Name the
pattern and its spread ("recurs across four language ports") instead of
pasting the paths that proved it.
