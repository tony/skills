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

- Runs the readiness gate: open, not draft, CI, mergeability, reviews.
- Waits on pending CI.
- Rebases and force-pushes if behind, after confirming.
- Merges via `gh pr merge`, pinned to the verified head commit, using repo
  history for the commit message.
- Checks out and pulls trunk.

### `/merge-pr:multiple`

Lands multiple PRs sequentially.

- Detects if PRs are a **stack** (merged bottom-up, children rebased/retargeted)
  or **independent** (merged in order, rebased on trunk).
- Between merges: rebases, force-pushes, waits on CI.
- Halts on CI failure, drift, or product-level conflicts, preserving merges.

## Merge strategy and flags

Defaults to merge commit; `--squash` and `--rebase` override. Other
`gh pr merge` flags pass through. The gate, strategy, and flag rules live in
`references/merge-readiness.md`.

## Prerequisites

- gh, authenticated with merge permissions.
- git, with fetch and push access to PR branches.
