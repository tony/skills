---
name: refresh-lock
description: "Use when refreshing Terraform or OpenTofu root lockfiles within existing constraints while preserving platform coverage."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[--root-module <dir>...] [--audit-only] [--no-commit]"
user-invocable: true
disable-model-invocation: true
---

# Refresh Terraform lock files

Re-resolve providers to the newest versions the existing constraints
allow, in every root module, and report what moved.

This changes no constraint. When a provider will not move, a constraint
is holding it; use `/terraform:bump-provider`.

Follow the conventions in `../bumping-terraform/SKILL.md` (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`../../references/layout-discovery.md` and `../../references/lock-and-init.md`.

User arguments: $ARGUMENTS

## Procedure

### 1. Discover every root module

Root modules come from the `.tf` files and from lock files tracked,
untracked, or gitignored, per `../../references/layout-discovery.md`. `--root-module` limits the run to
the named directories. Report nothing to refresh only when no directory
has a backend or a lock file. A directory with a backend or an untracked
or ignored lock but no committed one is a finding, not an absence.

### 2. Record the starting state

Per root module: the version selected for each provider, and how many
platforms each provider's entry tracks (the lock reference has the
count command). The first reports what moved; the second detects a
narrowed file. In an audit, also report the platform names the repository's CI and task
files pass to `providers lock` (the lock reference has the command), or
that none are recorded.

### 3. Present the plan and wait

Per the umbrella's Orchestration Plan, show the root modules to be refreshed and how many platforms each lock
tracks. With `--audit-only`, stop here and write nothing.

### 4. Refresh, one root module at a time

Apply the lock reference's guard to each root module: the lock must be
committed and unmodified, else skip and report it. Then run its
`init -upgrade` command (this skill moves every provider its constraints
allow) and compare each lock with `lockctl.py diff --allow '*'` against
its committed copy (the lock reference has the command); a non-zero exit
means a count dropped or a provider block vanished. When a count dropped, restore the platforms from the
names the lock reference finds in the repository's CI and task files, or
ask. If the count is still short, or the question goes unanswered
(headless included), restore that lock from git, leave it out of the
commit, list the root module under `## Failures` with the before and
after counts, and stop after the other root modules finish.

A root module whose `init` fails has its lock restored from git, and the
others carry on. Record the failure and continue.

### 5. Commit

One commit for the lock files that kept every platform (or got the
user's explicit yes), kept out of any commit carrying authored changes. With `--no-commit`, leave them in the working tree and say what
would have been committed. Write the message and the report per
`../../references/prose-rules.md`.

### 6. Verify and report

Read each lock back and compare the selected versions to the starting
state. Report per root module what moved, what did not, and, where a
provider stayed put, whether a constraint is holding it.

Run the detected tool's `fmt -check -recursive` (`tofu` where OpenTofu
drives the repository) and the repository's own gates. Never report a
gate as passing without reading the output that says so.

## Output

Open with a one-line hero (`✓ N of M lock files moved` or `Audit
only: M lock files found`), then these sections in order:

1. `## Root modules`: every one discovered, any directory with a
   backend but no committed lock file, and in an audit the platform
   names CI passes to `providers lock`.
2. `## Changes`: per root module and provider: the version before and
   after, and the platform count tracked before and after.
3. `## Held back`: providers that did not move, and the constraint
   holding each. In an audit, only providers a constraint is already
   blocking; omit the section otherwise.
4. `## Verification`: the gates run and their real results.
5. `## Failures`: root modules that could not be refreshed, and why.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 1 of 2 lock files moved

## Root modules

- envs/prod and envs/staging; tools/scratch has a backend but no committed lock file.

## Changes

- envs/prod: aws 6.56.1 to 6.56.4, random unchanged; 3 platforms before and after.

## Held back

- envs/staging: aws stays at 6.56.1, held by a ~> 6.56.0 cap in modules/network.

## Verification

- fmt -check passes.
```

A run that cannot proceed ends with the stopped line from
`../bumping-terraform/SKILL.md`, not this shape.

End with an `AskUserQuestion` panel offering next steps, for example:
bump a constraint that is holding a provider back, restore
multi-platform coverage, commit an untracked lock file, or stop here.
Skip the panel only in plan mode. Without a question tool, list the
options and stop.
