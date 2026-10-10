---
name: terraform-refresh-lock
description: >-
  Use when refreshing Terraform or OpenTofu root lockfiles within existing
  constraints while preserving platform coverage.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--root-module <dir>...] [--audit-only] [--no-commit]"
  source: "plugins/terraform/skills/refresh-lock/SKILL.md"
---

# Refresh Terraform lock files

Re-resolve provider selections in every root module under the existing
constraints, and report the changes read back from the locks.

This changes no constraint. When a constraint blocks a confirmed newer
release, use the `terraform-bump-provider` skill; an unchanged selection alone
does not establish that a constraint is responsible.

Follow the conventions in the `terraform-bumping-terraform` skill (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`references/layout-discovery.md` and `references/lock-and-init.md`.

User arguments: $ARGUMENTS

## Procedure

### 1. Discover every root module

Root modules come from configuration files and from lock files tracked,
untracked, or gitignored, per `references/layout-discovery.md`. `--root-module` limits the run to
the named directories. Report nothing to refresh only when no directory
has a backend or a lock file. A directory with a backend or an untracked
or ignored lock but no committed one is a finding, not an absence.

### 2. Record the starting state

Per root module: the version selected for each provider and its `h1:`
checksum count (the lock reference has the command). The count detects
checksum loss; it does not establish platform coverage. Record the
platform names the repository's CI and task files pass to `providers lock`
(the lock reference has the command), when
they pass any; include those declared names in an audit without claiming
they were checked.

### 3. Present the plan and wait

Per the umbrella's Orchestration Plan, show the root modules to be refreshed,
each provider's `h1:` count and the declared platform names. With
`--audit-only`, answer using the audit form under Output; run no refresh
or check that writes files.

### 4. Refresh, one root module at a time

Apply the lock reference's guard to each root module: the lock must be
committed and unmodified, else skip and report it. Then run its
`init -upgrade` command to re-resolve all provider selections. Check the
declared platform names with `providers lock` for changed
providers, per the lock reference, then compare each lock with
`lockctl.py diff --allow '*'` against its committed copy; a non-zero exit
means an `h1:` count dropped or a provider block vanished. A count drop
needs the required platform names from CI/task files or the user. If the
count is still short without explicit approval for that file's reduction,
or the question goes unanswered (headless included), restore that lock from
git and leave it out of the commit. When other
root modules were refreshed, list this one under `## Failures` with the
before and after counts; when none were, end with the stopped line.
When the names were not found, the stopped step asks for them and
says nothing about where the search looked or what it did not find.
The step ends with its request, with no "and I'll refresh it again" clause.
When no other root module was refreshed and the lock is restored, the reply
reads:

```text
⚠ Stopped: refreshing infra/prod would drop random's h1 records from 2 to 1, so its lock was restored and nothing was committed.

Which platform names must infra/prod's lock cover?
```

A root module whose `init` or declared-platform package check fails has
its lock restored from git, and the others carry on. Record the failure
and continue.

### 5. Verify, then commit

Verify on the working tree before any commit. Read each lock back and
compare the selected versions to the starting state. Report per root
module what moved, what did not, and, where a provider stayed put,
whether a constraint is holding it.

Run the detected tool's `fmt -check -recursive` (`tofu` where OpenTofu
drives the repository) and the repository's own gates. Never report a
gate as passing without reading the output that says so. Apply
[Verification gates](references/lock-and-init.md#verification-gates)
to classify failures before publication. When it requires a stop, leave the
refreshed locks in the working tree, commit nothing, and end with the
stopped line (the umbrella has its mid-run form).

Then make one commit for locks that passed the checks, including any
explicitly approved checksum-count reduction, kept out of any commit
carrying authored changes. With `--no-commit`, leave them in the working tree. Name the
commit by subject in the report, never by SHA. Write the message and the
report per `references/prose-rules.md`.

## Output

Open with a one-line hero (`✓ N of M lock files moved`, `✓ 1 of 1 lock
file moved` when M is 1, or `Audit only: M lock files found`), then these sections in order:

1. `## Root modules`: every one discovered, any directory with a
   backend but no committed lock file. In an audit, each provider's
   selected version and `h1:` count belong here, followed by
   `platform coverage unverified`. Include any CI platform names as
   declared names; an audit does not check their packages.
2. `## Changes`: after a refresh, per root module and provider: the
   version before and after and the `h1:` checksum counts before and
   after. Give the platform names whose package checks passed and where
   the required names came from, or coverage unverified.
3. `## Held back`: providers that did not move and the confirmed reason,
   such as a constraint or mirror limit. In an audit, include only a
   confirmed restriction, never a predicted move based on a permissive
   range; omit the section otherwise.
4. `## Verification`: the gates run and their real results.
5. `## Failures`: root modules that could not be refreshed, and why.

An audit reports current state in this shape; omit sections with no results:

```text
Audit only: 1 lock file found

## Root modules

- envs/prod: aws 5.60.0 with 3 h1 records; random 3.6.0 with 1 h1 record; platform coverage unverified.

Next steps:

- Refresh envs/prod
- Confirm the required platform names
- Stop here
```

After a refresh, use this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 1 of 2 lock files moved

## Root modules

- envs/prod and envs/staging; tools/scratch has a backend but no committed lock file.

## Changes

- envs/prod: aws 6.56.1 to 6.56.4, 3 h1 records before and after; package checks passed for CI-required linux_amd64, linux_arm64 and darwin_arm64. Random unchanged.

## Held back

- envs/staging: aws 6.56.4; confirmed release 6.57.0 is excluded by ~> 6.56.0 in modules/network.

## Verification

- fmt -check passes.
```

A run that cannot proceed ends with the stopped line from
the `terraform-bumping-terraform` skill, not this shape, and has no
panel and no `Next steps:` list.

End with an `ask-user-choice` panel offering next steps, for example:
bump a constraint that is holding a provider back, restore
multi-platform coverage, commit an untracked lock file, or stop here.
Skip the panel only in plan mode. Without a question tool, print the
umbrella's `Next steps:` list and stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
