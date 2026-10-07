---
name: terraform-refresh-lock
description: >-
  Use when refreshing Terraform or OpenTofu root lockfiles within existing
  constraints while preserving platform coverage.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[--root-module <dir>...] [--audit-only] [--no-commit]"
  source: "plugins/terraform/skills/refresh-lock/SKILL.md"
---

# Refresh Terraform lock files

Re-resolve providers to the newest versions the existing constraints
allow, in every root module, and report what moved.

This changes no constraint. When a provider will not move, a constraint
is holding it; use the `terraform-bump-provider` skill.

Follow the phase structure and conventions in
the `terraform-bumping-terraform` skill (recorded tree state, commit
message rules, non-interactive defaults, stopped and audit-only runs). This skill uses
`references/layout-discovery.md` and `references/lock-and-init.md`.

User arguments: $ARGUMENTS

`references/lockctl.py` resolves from this skill's directory: print its absolute path once and write that path literally in each command, since shell variables do not persist between Bash calls.

## Procedure

### 1. Discover every root module

Run the umbrella's discovery phase first: root modules come from the
`.tf` files and from lock files tracked, untracked, or gitignored, per
`references/layout-discovery.md`. `--root-module` limits the run to
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

Show the root modules to be refreshed and how many platforms each lock
tracks. With `--audit-only`, stop here and write nothing.

### 4. Refresh, one root module at a time

Apply the lock reference's guard to each root module: the lock must be
committed and unmodified, else skip and report it. Then run its
`init -upgrade` command (this skill moves every provider its constraints
allow) and compare each lock's per-provider platform count against its
count before. When a count dropped, restore the platforms from the
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
`references/prose-rules.md`.

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
the `terraform-bumping-terraform` skill, not this shape.

End with an `ask-user-choice` panel offering next steps, for example:
bump a constraint that is holding a provider back, restore
multi-platform coverage, commit an untracked lock file, or stop here.
Skip the panel only in plan mode. Without a question tool, list the
options and take the default: stop here, without a closing line that
says the run stopped.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
