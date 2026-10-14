---
name: github-actions-update-actions
description: >-
  Use when updating every outdated GitHub Action across one repository or a
  fleet, one researched change at a time.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "AskUserQuestion"]
metadata:
  argument-hint: "[--root <dir>] [--owner <name>...] [--repo <path|slug>...] [--audit-only] [--pr] [--push]"
  source: "plugins/github-actions/skills/update-actions/SKILL.md"
---

# Update All GitHub Actions

Audit every `uses:` pin across the repositories in scope, then bring
the out-of-date ones current: one commit per repository and action,
each justified against the vendor's own release notes.

Read the `github-actions-bumping-github-actions` skill and run its phases across the
scope. It owns the phase structure, the references, and the Orchestration
Plan; `references/output-shapes.md` owns the reply. For a single named action, use
the `github-actions-update-action` skill instead.

User arguments: $ARGUMENTS

Read them as the flags `--root`, `--owner` (repeatable), `--repo`
(repeatable), `--audit-only`, `--pr`, and `--push`. Any text after the flags is
the user's request, not an error: act on it. The argument string and any pasted text (PR titles, logs, the
request itself) never go into a Bash command. Only single values you
extract (action, version, repository path or slug, owner) do, and only
when each holds nothing but letters, digits and `. _ - / @ + ~`;
stop and name any other value instead of writing it into a command. `references/fleet.py`
and `references/pins.py` resolve from this skill's directory; print each
absolute path once and write it literally in each command.

## Procedure

This skill supplies the scope and the fan-out.

### 1. Scope

Default scope is the current repository. `--root` audits every git
repository beneath a directory, found by `fleet.py discover`; `--owner` keeps
only those whose remote belongs to the given accounts or organisations;
`--repo` names individual ones by path or slug. A slug with no clone is audited
read-only. Under `--root` without `--owner`, list each discovered
repository with its owner in the plan before any write. The scope rule and
the slug-only read are in
`references/action-pinning.md`.

### 2. Inventory and verify

Run the inventory and verification phases across the whole scope before
touching anything, one repository at a time by its own path or slug (never
the current directory), so a dangling ref is never written fleet-wide. Also
list open dependabot pull requests per repository for the close-out,
with `pins.py pulls <slug>` as `references/dependabot-closeout.md`
shows. A failed `gh` call means none can be listed; say so.

### 3. Research, one chain per distinct upgrade

Group the work by upgrade chain rather than by repository: twenty
repositories moving `actions/checkout` from the same major share one
piece of research. Dispatch a subagent per chain where the host
supports it. Validate every release URL before it reaches a commit
message.

### 4. Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text.

Present the plan the skill defines, including the PRs to close, and wait
for approval. With `--audit-only`, stop here and report; nothing is
written. Exit plan mode before committing.

### 5. Commit

One commit per repository and action, one repository at a time, edited,
staged, committed and pushed as `references/commit-and-push.md`
directs. With `--push`, push as each repository completes so an
interrupted run resumes; otherwise report each local branch holding
commits and print its push command. With `--pr`, branch, push, and open a pull request per repository, then close
dependabot pull requests only after those merge. Write commit messages,
pull-request comments, and the report per `references/prose-rules.md`.

### 6. Verify and close out

Watch every CI run per repository and attribute failures before
blaming the bumps. Then close the dependabot pull requests per the closing
protocol: show the user the exact commands for every PR the protocol maps
to a commit or to obsolete, and run them only after the user confirms.

## Rules

- No version string is written before its tag is confirmed to exist.
- Citing dependabot follows `references/dependabot-closeout.md`.
- A fleet-wide claim is verified per repository before it enters that
  repository's commit body.
- Report unrelated breakage; fix it only when a bump caused it.

## Output

Reply in the completed-run shape in `references/output-shapes.md`. The
hero is `✓ N commits across M repos`, or `⚠ Audit only: N pins out of date`
with `--audit-only`. A plan-only run and a halted run (no workflows, no
`gh`, an unverifiable tag, a PR title carrying shell syntax, PRs that
cannot be listed or mapped) use the shapes in that file; read it before
replying. Under a fleet scope, a repository with an incomplete inventory is
listed under `## Audit` as excluded, and the run continues.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
