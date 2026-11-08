# repo-skills

Derive a repository's own agent skills from its docs, git history, CI,
shell history, and AI transcripts, test each with and without itself,
and land them in two commits.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install repo-skills --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install repo-skills@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add repo-skills@skills
```

Claude Code uses a leading slash (`/repo-skills:…`). Codex omits it (`repo-skills:…`).

## Skills

Gather the evidence, plan the skill set, test each skill without and with
itself, then commit the skills and the `.claude/skills` link:

```text
/repo-skills:derive [<repo path>] [--prefix <name>] [--since <date>]
```

It runs only when invoked by name, since it reads every local AI
transcript and the shell history and then commits. `--dry-run` stops
after the plan. `--no-transcripts` and `--no-shell-history` skip those
sources.

## What it writes

Skills land in `.agents/skills/<prefix>-<area>/SKILL.md`, the directory
Codex and other agents read, with a paragraph in `AGENTS.md` naming it.
The second commit makes `.claude/skills` one link to `../.agents/skills`,
so a skill added later needs no link of its own.

The categories it weighs (setup, architecture, style, gates,
dependencies, review, commits and pull requests, live checks, doc
checks, and repository-specific tasks), and the evidence each needs, are
in `references/skill-catalog.md`.

## Prerequisites

- python 3.14 or newer (standard library only), for `scripts/evidence.py`
- git
- `uvx`, to run the pinned `agentgrep` over local AI transcripts; without
  it the transcript source is reported unavailable
- sub-agents on the host, for testing each skill without and with itself

## Evidence and the link

`scripts/evidence.py` gathers what is deterministic. `paths` lists every
checkout sharing the origin, earlier session directories, and the
transcript globs covering them, so a repository that moved is still
searched under its old path. `git` summarises commit forms, merge shape,
and hot paths. `shell` attributes zsh, bash, and fish history to the
repository, ignoring lines a test harness wrote into a shared history
file. `transcripts` groups an agentgrep export by directory and keeps
the human-typed prompts. `link` replaces per-skill links under
`.claude/skills` with one directory link and refuses when real skill
directories are there.

`references/evidence-sources.md` covers reading each source and what
never leaves the machine. `references/testing-skills.md` covers the
with-and-without runs.
