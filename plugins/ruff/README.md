# ruff

Upgrade Ruff across repositories. Resolves new rules against each repo's
select list and creates one reviewed commit per rule, citing the upstream
rule doc.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install ruff@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add ruff@skills
```

Claude Code uses a leading slash (`/ruff:…`). Codex omits it (`ruff:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/ruff:bump [version]` | `ruff:bump [version]` | Raise the ruff floor across the repositories in scope and absorb what the release surfaces, one commit per rule |

Defaults to the latest stable release in the current repository, creating
a PR from a throwaway worktree.

**Arguments:**
- `--root <dir>`: Sweep every repository beneath a directory.
- `--repo <path|slug>...`: Target specific repositories.
- `--owner <name>`: Filter by account ownership.
- `--branch <name>`: Name the working branch.
- `--audit-only`: Report predicted work without making changes.
- `--adopt-defaults`: Carry through the default-rule-set change.
- `--push`: Push each branch after confirmation; without `--push` or `--pr`, stop after local commits and print the push command.
- `--pr`: Push and open a pull request.
- `--no-changelog`: Skip the changelog entry.

## Components

| Path | Purpose |
|------|---------|
| `skills/bump/SKILL.md` | The skill |
| `references/release-triage.md` | Sorting a release, intersecting with configuration, and grading fixes |
| `references/pin-sites-and-gating.md` | Pin sites, diagnosing, and gating resolvers |
| `references/default-rule-set.md` | Measuring default rule set cost and curating adoption |
| `references/prose-rules.md` | Rules for commit, PR, and report prose |

## Prerequisites

- `git` (with remote push access)
- GitHub CLI, authenticated
- Project's resolver and quality-check commands (defined in `AGENTS.md`/`CLAUDE.md` or CI workflow)
