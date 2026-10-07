# github-actions

Update GitHub Actions pins fleet-wide. Verifies tags, researches release
notes, commits each action separately, and supersedes Dependabot PRs.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install github-actions@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add github-actions@skills
```

Claude Code uses a leading slash (`/github-actions:…`). Codex omits it (`github-actions:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/github-actions:update-action <owner/action>` | `github-actions:update-action <owner/action>` | Take one named action to its current version wherever it is pinned — verify the tag, research the span, commit per repository |
| `/github-actions:update-actions` | `github-actions:update-actions` | Audit every action in scope and update the out-of-date ones, then close the dependabot PRs those commits superseded |

- `update-action`: Update a single known out-of-date action.
- `update-actions`: Audit across a repo or fleet. Use `--audit-only` to
  report without writing.

Defaults: Current repository, commit on default branch, no push.
Flags:
- `--pr`: Branch and open a PR.
- `--push`: Push the commits; without it, the report prints the push command.
- `--root <dir>`: Sweep every repo beneath a directory
  (`update-actions` only).
- `--owner <name>`: Keep only repos belonging to given accounts
  (`update-actions` only).

## Why not just merge dependabot's PRs

Dependabot opens PRs with generated messages and no context. This plugin
researches the span between your pin and the target, writes the rationale
into a commit on the default branch, and closes the bot's PR with a
reference to that commit. (The PR references the commit, not vice versa).

## Pinning

- **Major-level floats (`@v7`)** (default): Preserve existing shape. Exact
  patch pins repin to the float if available.
- **Commit SHA pins**: Keep their shape, resolving the tag's commit SHA
  (annotated tags dereferenced) and moving the trailing version comment
  alongside it.
- **No floating major**: Pin to the exact release, explaining why in the
  commit body.

## Shared references

All three skills read `references/action-pinning.md` and
`references/dependabot-closeout.md`; the worktree and prose rules are shared references.

## Skill

`bumping-github-actions` triggers automatically when discussing out-of-date
actions or dependabot's action PRs. `update-action` and `update-actions`
are explicit entry points to the same procedure.

## Scope

- **Own repositories only**: Forks are detected and skipped. Local
  (`./`) and `docker://` references are skipped.
- **Fixes only bumps**: Pre-existing breakage (e.g., lint failures) is
  reported, not fixed.

## Prerequisites

- **git** — Reads workflow content from the default branch.
- **gh** — Tag verification, release lookup, CI watching, and closing
  dependabot PRs.
