# skill-style

Deletion-test trimmer and auditor for SKILL.md files.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install skill-style --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

Routes while a SKILL.md is being written, and takes targets when
invoked by name (`/skill-style:skill-style <paths>`). It edits the
targets in place, shows a diff against a pre-edit snapshot, and
renders the reply (opening, ledger, diff) with `scripts/skill_diff.py`.
It never commits, pushes, or scans the
repository unprompted.

Flags: `--audit` reports the ledger and writes nothing to the targets; `--diff-only`
shows the edits without writing them. A SKILL.md pasted inline is
trimmed without confirmation or git.

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

- `python3` (3.9 or newer) runs `scripts/skill_diff.py`.
- Reads `AGENTS.md` / `CLAUDE.md` at runtime to match repo voice.
