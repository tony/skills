# ruff

Upgrade Ruff across repositories. Resolves new rules against each repo's
select list and creates one reviewed commit per rule, citing the upstream
rule doc.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install ruff --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

### bump

Raise the ruff floor across the repositories in scope and absorb what the
release surfaces, one commit per rule. Claude Code invokes it as
`/ruff:bump [version]`, Codex as `ruff:bump [version]`.

Invoke it by name only; the model never starts it on its own (`disable-model-invocation: true`).

Defaults to the latest stable release in the current repository, committing
on a branch in a throwaway worktree. Add `--push` or `--pr` to publish.

Arguments:

- `--root <dir>`: Sweep every repository beneath a directory.
- `--repo <path|slug>...`: Target specific repositories.
- `--owner <name>...`: Filter by account ownership.
- `--branch <name>`: Name the working branch.
- `--audit-only`: Report predicted work without writing to the checkout.
- `--adopt-defaults`: Carry through the default-rule-set change, including in a repository already on the target version.
- `--push`: Push each branch after confirmation; without `--push` or `--pr`, stop after local commits and print the push command.
- `--pr`: Push and open a pull request.
- `--no-changelog`: Skip the changelog entry.

## Components

- `skills/bump/SKILL.md`: the skill
- `references/release-triage.md`: sorting a release, intersecting with configuration, and grading fixes
- `references/pin-sites-and-gating.md`: pin sites, diagnosing, and gating resolvers
- `references/default-rule-set.md`: measuring default rule set cost and curating adoption
- `references/cooldown-exemption.md`: exempting one package from a resolver cooldown
- `references/throwaway-worktree.md`: working on a branch in an isolated worktree
- `references/prose-rules.md`: rules for commit, PR, and report prose
- `references/reply-shape.md`: the reply's sections, required facts, and templates
- `scripts/default_delta.py`: per-rule finding delta between the configured rule set and the recommended default-set shape (measured in a scratch copy), that shape written into a repository with `--apply`, and the findings a version reports at locations a pre-bump snapshot lacked
- `scripts/ruff_pins.py`: ruff pin sites in a tree, resolved versions from lockfiles compared with a target, and the time a resolver cooldown lapses, and the repositories in scope

## Prerequisites

- `git`; remote push access only for `--push` or `--pr`
- `curl`, or GitHub CLI (`gh`) for release lookups; `gh`, authenticated, only for fork checks and `--pr`
- `jq`, for resolving a rule's documentation slug in `references/default-rule-set.md`
- `python3` (3.14 or newer) for the bundled measurement script
- Project's resolver and quality-check commands (defined in `AGENTS.md`/`CLAUDE.md` or CI workflow)
