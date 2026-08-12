# merge-pr

Merge PRs matching repo history conventions. Includes readiness checks,
CI watching, stack detection, and automated rebasing.

Merging is a separate act: verify checks, sync trunk, land branch. It never tags,
edits changelogs, or claims releases.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install merge-pr@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add merge-pr@skills
```

Claude Code uses a leading slash (`/merge-pr:…`). Codex omits it (`merge-pr:…`).

## Components

### `/merge-pr:this`

Merges a single PR. 
- Runs readiness gates (open, CI passing via `gh pr checks`).
- Waits on pending CI.
- Rebases and force-pushes if behind.
- Merges via `gh pr merge` using repo history for commit messages.
- Checks out and pulls trunk.

### `/merge-pr:multiple`

Lands multiple PRs sequentially. 
- Detects if PRs are a **stack** (merged bottom-up, children rebased/retargeted)
  or **independent** (merged in order, rebased on trunk).
- Between merges: rebases, force-pushes, waits on CI.
- Halts on CI failure, drift, or product-level conflicts, preserving merges.

## Merge strategy and flags

- Defaults to merge commit. `--squash` and `--rebase` override.
- Passes other `gh pr merge` flags verbatim (e.g., `--delete-branch`, `--admin`). 
- `--admin` only bypasses branch protection for green CI; never merges over failing checks.
- Adheres to `references/merge-readiness.md` rules: discover, ask on ambiguity, halt on surprise.

## Prerequisites

- **gh**: Authenticated with merge permissions.
- **git**: Fetch/push access to PR branches.
