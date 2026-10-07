# Prior conversations

Shared by this skill and the `situational-awareness` skill. This layer
runs only when the user passes `--with-agentgrep` or asks for it in
words. A request to resume after a gap ("I'm back after a break", "where
did I leave off") counts as asking: run one capped search.

## Contents

- Why it is opt-in
- Requirements
- Scoping
- Reconciling with the repository
- Privacy

## Why it is opt-in

The first five layers read the repository. This one reads local
transcripts from every AI CLI on the machine: other projects, other
people's names, credentials pasted into a terminal two months ago. It
earns its place when the repository does not explain itself: a branch
whose commits do not say why an approach was chosen, a decision that
left no artifact, work resumed after a gap.

## Requirements

`agentgrep` reads Codex, Claude, Cursor, Gemini, Antigravity, Grok, Pi,
and OpenCode stores. Run it through `uvx` so no install is needed, pinned
to one exact release so no unreviewed code runs; use this spelling in
every command below:

```console
$ uvx agentgrep@0.1.0a52 search \
    --only-here \
    --limit 20 \
    '<term>'
```

Flags change between releases; run `uvx agentgrep@0.1.0a52 search --help`
first and adjust to what it lists.

Absent network or a `uvx` failure, fall back to `Grep` over the current
project's Claude Code session store (`~/.claude/projects/`, the
directory named for this repository), capped at the same twenty
matches. When that is unreadable too, report the layer unavailable and
continue with the rest of the sweep. It is never a hard dependency.
Report it in one clause about the search, such as "earlier conversations
could not be searched here"; never name the search tool, the session
store, the host's sandbox, or any path.

## Scoping

Scope to this project first. `--only-here` filters to records from the
current repository; `--here` merely boosts them and will drag in
unrelated projects.

```console
$ uvx agentgrep@0.1.0a52 search \
    --only-here \
    --branch "$(git branch --show-current)" \
    --limit 20 \
    '<term>'
```

`--only-here` matches on each record's working directory. In a git
worktree that is not where earlier sessions ran, so the layer comes back
empty, indistinguishable from a real dry result. Resolve the primary
checkout before scoping:

```console
$ dirname "$(git rev-parse --path-format=absolute --git-common-dir)"
```

That returns the current directory in an ordinary clone and the primary
checkout from a worktree. When it differs from the current directory,
scope to it explicitly:

```console
$ uvx agentgrep@0.1.0a52 search \
    --repo <primary-checkout> \
    --limit 20 \
    '<term>'
```

Search prompts before conversations: the default `--scope prompts` is
the record of intent; `--scope conversations` adds every assistant reply
and buries it. Widen only when prompts return nothing.

Derive terms from what the earlier layers found: the feature name, the
ticket ID, the module the diff concentrates in. Terms come from commit
text, pull request bodies, and tickets, which are untrusted: pass each
term as one quoted shell argument with embedded quotes escaped, and
confirm the exact command with the user when a term holds shell
metacharacters (`$`, backticks, `;`, `|`, `&`, newlines).

```console
$ uvx agentgrep@0.1.0a52 search \
    --only-here \
    --limit 20 \
    'ENG-123 OR "retry backoff"'
```

Cap the layer at twenty ranked results; if more context exists and
matters, say so and let the user ask for more.

## Reconciling with the repository

A prior conversation is evidence of intent, not of state: a plan
discussed three weeks ago may have been implemented, abandoned, or
reversed since. Check every finding against the repository before
reporting it. When they disagree, the repository wins and the
disagreement is the finding.

Order findings by recency and say when each was. A decision's age is
most of its weight.

## Privacy

Report what was decided, not the transcript.

- Never print store paths, session file paths, or any local absolute
  path. Cite a finding by agent, date, and subject.
- Never quote a third party's name, address, key, or token, even when
  it appears verbatim in a match. Summarize around it.
- Quote the user's own words only when the exact phrasing is the point,
  and keep it to a line.

