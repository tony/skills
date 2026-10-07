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
| `/github-actions:update-action <owner/action> [target version]` | `github-actions:update-action <owner/action> [target version]` | Take one named action to its current version wherever it is pinned — verify the tag, research the span, commit per repository |
| `/github-actions:update-actions` | `github-actions:update-actions` | Audit every action in scope and update the out-of-date ones, then close the dependabot PRs those commits superseded |

- `bumping-github-actions`: the shared procedure; it also triggers on its
  own when you mention out-of-date actions or Dependabot's action PRs.

By default a run covers the current repository, commits to the default
branch, and does not push. Flags:

- `--repo <path|slug>`: name repositories to cover; repeatable.
- `--root <dir>`: sweep every repository beneath a directory
  (`update-actions` only).
- `--owner <name>`: keep only repositories owned by the given accounts
  (`update-actions` only).
- `--audit-only`: report without writing (`update-actions` only).
- `--pr`: branch and open a pull request instead of committing to the
  default branch.
- `--push`: push the commits; without it, the report prints the push
  command.

Pinning rules, the fork rule, and the Dependabot close-out protocol live in
`references/action-pinning.md` and `references/dependabot-closeout.md`.

## Prerequisites

- git: reads workflow content from the default branch.
- gh: tag verification, release lookup, CI watching, and closing
  dependabot PRs.
