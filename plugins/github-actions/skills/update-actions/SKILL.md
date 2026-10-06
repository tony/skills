---
name: update-actions
description: "Use when updating every outdated GitHub Action across one repository or a fleet, one researched change at a time."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Task", "AskUserQuestion"]
argument-hint: "[--root <dir>] [--owner <name>...] [--repo <path|slug>...] [--audit-only] [--pr] [--push]"
user-invocable: true
disable-model-invocation: true
---

# Update All GitHub Actions

Audit every `uses:` pin across the repositories in scope, then bring
the out-of-date ones current: one commit per repository and action,
each justified against the vendor's own release notes.

Read `../bumping-github-actions/SKILL.md` and run its phases across the
scope. It owns the phase structure, the references, the Orchestration
Plan, and the output shape. For a single named action, use
`/github-actions:update-action` instead.

User arguments: $ARGUMENTS

## Procedure

This skill supplies the scope and the fan-out.

### 1. Scope

Default scope is the current repository. `--root` audits every git
repository beneath a directory; `--owner` keeps only those whose remote
belongs to the given accounts or organisations; `--repo` names
individual ones. The fork rule is in
`../../references/action-pinning.md`.

### 2. Inventory and verify

Run the inventory and verification phases across the whole scope before
touching anything, so a dangling ref is never written fleet-wide. Also
list open dependabot pull requests per repository for the close-out,
with the command in `../../references/dependabot-closeout.md`. A failed
`gh` call means none can be listed; say so.

### 3. Research, one chain per distinct upgrade

Group the work by upgrade chain rather than by repository: twenty
repositories moving `actions/checkout` from the same major share one
piece of research. Dispatch a subagent per chain where the host
supports it. Validate every release URL before it reaches a commit
message.

### 4. Orchestration plan

Present the plan the skill defines, including the PRs to close, and wait
for approval. With `--audit-only`, stop here and report; nothing is
written.

### 5. Commit

One commit per repository and action, one repository at a time. With
`--push`, push as each completes so an interrupted run resumes; otherwise
print the push commands in the report. Write commit messages,
pull-request comments, and the report per `../../references/prose-rules.md`.
No `Co-Authored-By`, no "Generated with" or other tool trailer, no emoji.

### 6. Verify and close out

Watch CI per repository and attribute failures before blaming the
bumps. Then close the dependabot pull requests per the closing
protocol: show the user the exact commands for every PR whose action was
bumped (citing its commit) or is no longer in any workflow (obsolete),
and run them only after the user confirms.

## Rules

- No version string is written before its tag is confirmed to exist.
- Commit messages never cite dependabot; the pull request cites the
  commit.
- A fleet-wide claim is verified per repository before it enters that
  repository's commit body.
- Report unrelated breakage; fix it only when a bump caused it.

## Output

Use the output shape in `../bumping-github-actions/SKILL.md`. The hero is
`✓ N commits across M repos`, or `⚠ Audit only: N pins out of date` with
`--audit-only`, or `⚠ Blocked: <reason>` with one sentence on what the
user must do when the run halts.
