# merge-pr

Merge PRs matching repo history conventions. Includes readiness checks,
CI watching, stack detection, and automated rebasing.

Merging is a separate act: verify checks, sync trunk, land branch. It never tags,
edits changelogs, or claims releases.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install merge-pr@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add merge-pr@skills
```

Claude Code uses a leading slash (`/merge-pr:…`). Codex omits it (`merge-pr:…`).

## Components

### `/merge-pr:this`

Merges a single PR.

Runs the readiness gate, rebases after confirming when behind, merges via
`gh pr merge` pinned to the verified head with a message matching repo
history (written through files, never a shell string), then syncs trunk and checks it contains the merge commit.

### `/merge-pr:multiple`

Lands multiple PRs sequentially.

- Detects if PRs are a **stack** (merged bottom-up, children rebased/retargeted)
  or **independent** (merged in order).
- Between merges: rebases and force-pushes only a PR that is behind or
  conflicting, and waits on CI. A stack parent is merged without
  `--delete-branch` so its child PR stays open; the parent branches are
  deleted after the last merge when you passed the flag.
- Halts on CI failure, drift, or product-level conflicts, preserving merges.

## Merge strategy and flags

The gate, strategy, and flag rules live in `references/merge-readiness.md`.

## Prerequisites

- gh, authenticated with merge permissions.
- git, with fetch and push access to PR branches.
