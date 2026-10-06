# skill-style

Hold SKILL.md files to a deletion test — a line stays only when its
removal would change what the agent does — while frontmatter, code
blocks, and sections survive verbatim.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install skill-style@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add skill-style@skills
```

Claude Code uses a leading slash (`/skill-style:…`). Codex omits it (`skill-style:…`).

## Components

### `skill-style`

Routes automatically while a SKILL.md is being written, and takes
targets when invoked by name (`/skill-style:skill-style <paths>`).
Invoked with targets, it trims the files in place and shows the diff;
it never commits, never pushes, and never scans the repository on its
own initiative.

Flags: `--audit` (report the ledger, change nothing), `--diff-only`
(show the proposed edits as a diff without writing them).

## The deletion test

A line stays only when its removal would change what the agent does.
Every line the test cuts is *true*; truth is not the bar.

The test never reaches frontmatter, fenced commands, literal commands,
section headings, or a warning on a destructive step. A command in a
skill is a quotation: editing its characters silently unverifies it,
so a flawed command is reported, not corrected. Only a fence's tag,
`$ ` prompt, and one-command-per-fence split follow the house policy.

## References

`references/skill-rubric.md` carries the full rule catalog: naming,
descriptions, progressive-disclosure budgets, degrees of freedom,
and anti-patterns, merged from Anthropic's
[skill authoring best practices][anthropic-best-practices] and
OpenAI's [build skills][openai-build-skills] guidance.

`references/example-bloated.md` is a full skill with its defects
named. `references/example-ideal.md` is the same skill after the test.

[anthropic-best-practices]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
[openai-build-skills]: https://developers.openai.com/plugins/build/skills

## Prerequisites

- None. Reads `AGENTS.md` / `CLAUDE.md` at runtime to match repo voice.
