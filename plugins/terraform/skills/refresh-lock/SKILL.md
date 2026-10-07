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

Follow the phase structure and conventions in
`../bumping-terraform/SKILL.md` (recorded tree state, commit
message rules, non-interactive defaults, stopped and audit-only runs). This skill uses
`../../references/layout-discovery.md` and `../../references/lock-and-init.md`.

User arguments: $ARGUMENTS

## Procedure

### 1. Discover every root module

List the committed lock files:

```console
$ git ls-files -- '*.terraform.lock.hcl'
```

No output means a module repository with nothing to refresh: report
nothing to refresh.

Run the umbrella's discovery phase. `--root-module` limits the run to the
named directories. A directory holding a backend block but no committed
lock file is a finding: its lock is untracked or was never created.

### 2. Record the starting state

Per root module: the version selected for each provider, and how many
platforms each provider's entry tracks (the lock reference has the
count command). The first reports what moved; the second detects a
narrowed file. In an audit, also report the platform names
`lockctl.py platforms` finds, or that none are recorded.

### 3. Present the plan and wait

Show the root modules to be refreshed and how many platforms each lock
tracks. With `--audit-only`, stop here and write nothing.

### 4. Refresh, one root module at a time

Apply the lock reference's guard to each root module: the lock must be
committed and unmodified, else skip and report it. Then run its
`init -upgrade` command (this skill moves every provider its constraints
allow) and compare each lock's per-provider platform count against its
count before. When a count dropped, restore the platforms from the
names `lockctl.py platforms` finds in the repository, or ask.

A root module whose `init` fails has its lock restored from git, and the
others carry on. Record the failure and continue.

### 5. Commit

One commit for the lock files, kept out of any commit carrying authored
changes. With `--no-commit`, leave them in the working tree and say what
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

1. `## Root modules`: every one discovered, and any directory with a
   backend but no committed lock file.
2. `## Changes`: per root module and provider: the version before and
   after, and the platform count tracked before and after.
3. `## Held back`: providers that did not move, and the constraint
   holding each.
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
options and take the default: stop here.
