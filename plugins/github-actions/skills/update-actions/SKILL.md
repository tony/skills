---
name: update-actions
description: "Use when updating every outdated GitHub Action across one repository or a fleet, one researched change at a time."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "WebSearch", "WebFetch", "Task", "AskUserQuestion"]
argument-hint: "[--root <dir>] [--owner <name>...] [--repo <path|slug>...] [--audit-only] [--pr] [--no-push]"
user-invocable: true
disable-model-invocation: true
---

# Update All GitHub Actions

Audit every `uses:` pin across the repositories in scope, then bring
the out-of-date ones current — one commit per repository and action,
each justified against the vendor's own release notes.

Run the phases of `../bumping-github-actions/SKILL.md` across the scope;
it names the references and owns the phase structure.

For a single named action, use `/github-actions:update-action` instead.

User arguments: $ARGUMENTS

## Procedure

Follow the skill's phases. This command supplies the scope and the
fan-out.

### 1. Scope

Default scope is the current repository. `--root` audits every git
repository beneath a directory; `--owner` keeps only those whose remote
belongs to the given accounts or organisations; `--repo` names
individual ones. The fork rule is in
`../../references/action-pinning.md`.

### 2. Inventory and verify

Run the skill's inventory and verification phases across the whole
scope before touching anything. Also list open dependabot pull requests
per repository for the close-out; a failed `gh` call means none can be
listed, so say so:

```console
gh pr list --author app/dependabot --state open --limit 50 --json number,title
```

 Every target tag is confirmed to exist
first; a dangling ref written fleet-wide is the expensive failure this
sequencing prevents.

### 3. Research, one chain per distinct upgrade

Group the work by upgrade chain rather than by repository — twenty
repositories moving `actions/checkout` from the same major share one
piece of research. Dispatch a subagent per chain where the host
supports it. Validate every release URL before it reaches a commit
message.

### 4. Orchestration plan

Present the plan the skill defines and wait for approval. With
`--audit-only`, stop here and report; nothing is written.

### 5. Commit and push

One commit per repository and action. Work through repositories one at
a time, pushing as each completes, so an interrupted run resumes
cleanly. Write commit messages, pull-request comments and the report per
`../../references/prose-rules.md`.

### 6. Verify and close out

Watch CI per repository. Attribute failures before blaming the bumps.
Close every dependabot pull request whose action was bumped, citing the
commit that superseded it; close as obsolete any whose action no longer
appears in a workflow.

## Rules

- No version string is written before its tag is confirmed to exist.
- Commit messages never cite dependabot; the pull request cites the
  commit.
- A fleet-wide claim is verified per repository before it enters that
  repository's commit body.
- Report unrelated breakage; fix it only when a bump caused it.

## Output

Open with a one-line hero (`✓ N commits across M repos` or
`⚠ Audit only: N pins out of date`), then exactly these sections:

1. `## Audit` — every action in scope with its current pins and the
   latest version, and what was excluded as fork, upstream, or already
   current.
2. `## Upgrades` — one entry per distinct chain: what changed, release
   links, and which repositories the breaking changes reach.
3. `## Commits` — per repository, the commits made and whether they
   were pushed.
4. `## Close-out` — CI results, dependabot pull requests closed with
   the commit each cited, and any failure shown to predate the bumps.
5. `## Drift` — repositories with no dependabot configuration, and
   actions pinned to a moving branch.

End with an `AskUserQuestion` panel offering next steps (for example:
add dependabot configuration to the repos lacking it, pin the moving
branches, stop here) — skip the panel only in plan mode.
