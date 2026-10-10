# github-actions

Update GitHub Actions pins fleet-wide. Verifies tags, researches release
notes, commits each action separately, and supersedes Dependabot PRs.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install github-actions --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

## Skills

Take one named action to its current version wherever it is pinned:
verify the tag, research the span, commit per repository.

```text
/github-actions:update-action <owner/action> [target version]
```

Audit every action in scope, update the out-of-date ones, then close the
dependabot PRs those commits superseded.

```text
/github-actions:update-actions
```

Codex omits the leading slash (`github-actions:update-action`). Each
skill's `argument-hint` lists its flags. By default a run covers the
current repository, commits to the default branch, and does not push. A
checkout that is dirty, on another branch, or on a detached HEAD gets its
commits on a local `wip/` branch instead.

`bumping-github-actions` is the shared procedure; it also triggers on its
own when you mention out-of-date actions or Dependabot's action PRs.

Pinning rules, the scope rule, commit and push boundaries, and the Dependabot
close-out protocol live in `references/action-pinning.md`,
`references/commit-and-push.md`, and `references/dependabot-closeout.md`.

## Prerequisites

- git: reads workflow content from the default branch.
- python3 (3.9 or newer): runs `scripts/pins.py`: the pin inventory, tag
  check, majors list, and pull-request proposal reader.
- gh: tag verification, release lookup, CI watching, and closing
  dependabot PRs.
