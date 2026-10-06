# github-actions

Update GitHub Actions pins fleet-wide. Verifies tags, researches release
notes, commits each action separately, and supersedes Dependabot PRs.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install github-actions@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add github-actions@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/github-actions:update-action <owner/action>` | `github-actions:update-action <owner/action>` | Take one named action to its current version wherever it is pinned — verify the tag, research the span, commit per repository |
| `/github-actions:update-actions` | `github-actions:update-actions` | Audit every action in scope and update the out-of-date ones, then close the dependabot PRs those commits superseded |

- `update-action`: Update a single known out-of-date action.
- `update-actions`: Audit across a repo or fleet. Use `--audit-only` to
  report without writing.

Defaults: Current repository, commit on default branch.
Flags:
- `--pr`: Branch and open a PR.
- `--no-push`: Commit locally and stop.
- `--root <dir>`: Sweep every repo beneath a directory
  (`update-actions` only).
- `--owner <name>`: Keep only repos belonging to given accounts
  (`update-actions` only).

## Why not just merge dependabot's PRs

Dependabot opens PRs with generated messages and no context. This plugin
researches the span between your pin and the target, writes the rationale
into a commit on the default branch, and closes the bot's PR with a
reference to that commit. (The PR references the commit, not vice versa).

## Workflow

1. **Inventory** — Read `uses:` lines from `.github/workflows/` and
   `.github/actions/` on the default branch.
2. **Verify** — Confirm the target tag exists before writing.
3. **Research** — Collect major releases and breaking changes between
   pin and target with verified links.
4. **Plan gate** — Confirm scope, targets, evidence, and commit count
   before writing.
5. **Commit** — One per repository and action, with upgrade rationale
   and release links in the body.
6. **Close out** — Watch CI, attribute failures, and close superseded
   dependabot PRs.

## Pinning

- **Major-level floats (`@v7`)** (default): Preserve existing shape. Exact
  patch pins repin to the float if available.
- **Commit SHA pins**: Keep their shape, moving the trailing version
  comment alongside the SHA.
- **No floating major**: Pin to the exact release, explaining why in the
  commit body.

## Shared references

Both commands and the skill read the same files to prevent drift:
- `references/action-pinning.md` — Inventory, tag verification, pin
  granularity, and per-repository gates.
- `references/dependabot-closeout.md` — Closing protocol, CI attribution,
  and scope discipline.

## Skill

`bumping-github-actions` triggers automatically when discussing out-of-date
actions or dependabot's action PRs. The commands are explicit entry points
to the same procedure.

## Scope

- **Own repositories only**: Forks are detected and skipped.
- **Fixes only bumps**: Pre-existing breakage (e.g., lint failures) is
  reported, not fixed.

## Prerequisites

- **git** — Reads workflow content from the default branch.
- **gh** — Tag verification, release lookup, CI watching, and closing
  dependabot PRs.
