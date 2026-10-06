# Merge Readiness and Merge Conventions

Shared contract for `/merge-pr:this` and `/merge-pr:multiple`. Both
commands read this file before touching any PR.

## Contents

- Readiness gate
- Rebase procedure
- Merge commit message
- Strategy and flag passthrough
- After each merge

## Readiness gate

A PR merges only after every check below is confirmed. When any of
them is ambiguous, do discovery first (read the PR, its checks, and
its branch), and if the answer is still unclear, ask the user rather
than guessing. Without a question tool (Codex, headless runs), halt and
report what is unclear.

- **Open and not draft**: `gh pr view <n> --json state,isDraft`.
  A draft or closed PR halts the run.
- **CI**: `gh pr checks <n>`. Pending checks (exit code 8) are waited on
  with `gh pr checks <n> --watch`. Failing checks halt the run: report
  the failing check and stop. A PR with no checks makes `gh pr checks`
  error with "no checks reported"; treat that as no CI to wait on and say
  so in the report. `--admin` never overrides failing or pending CI.
- **Mergeability**: `gh pr view <n> --json mergeable,mergeStateStatus`.
  - `CLEAN` and `HAS_HOOKS` pass.
  - `DIRTY` (conflicts with the base) and `BEHIND` (the base has moved)
    route through the rebase procedure below before merging.
  - `UNKNOWN` means GitHub has not computed the state yet, common right
    after a push. Re-run the command up to three times, a few seconds
    apart; if it is still `UNKNOWN`, halt.
  - `BLOCKED` means a protection rule is unmet. Halt and name the rule
    (usually a required review or check); apply the `--admin` policy
    below only if that is the sole blocker.
  - `UNSTABLE` means non-required checks are failing. Surface them and
    ask before merging.
  - `DRAFT` halts.
- **Reviews**: `gh pr view <n> --json reviewDecision`. A
  `CHANGES_REQUESTED` decision halts the run and is surfaced to the
  user; it is their call, not the command's.
- **Situational awareness**: skim the PR title, body, and recent
  commits (`gh pr view <n>`, `gh pr view <n> --json commits`) so the
  merge commit message describes what actually ships and so surprises
  (WIP markers, "do not merge" labels, unresolved review threads the
  user mentioned) surface before the merge, not after.

## Rebase procedure

When a PR is `BEHIND` or `DIRTY`, or an earlier merge in a multi-PR
run has moved trunk. Consent differs by command on purpose:
`/merge-pr:this` confirms before rebasing — a rebase expands "merge
this PR" — while `/merge-pr:multiple`'s between-merge rebases are
its disclosed core loop, covered by the roster shown up front.

1. Check that the working tree is clean (`git status --porcelain` prints
   nothing); if not, halt and ask the user to commit or stash. Note the
   current branch (`git branch --show-current`) so it can be restored.
   A fork PR (`gh pr view <n> --json isCrossRepository,maintainerCanModify`)
   with `maintainerCanModify` false cannot be pushed to: halt and say the
   author must rebase.
2. Check out the PR branch (`gh pr checkout <n>`), fetch, then
   rebase it onto its current base. For a stacked PR whose parent
   just merged, drop the parent's commits with
   `git rebase --onto <base> <old-parent-head> <branch>`.
3. Resolve conflicts. Mechanical resolutions (context drift, adjacent
   hunks, a list both sides appended to) are resolved directly. A
   conflict that forces a choice between two competing behaviors is
   presented to the user via `AskUserQuestion` — never silently pick
   a side.
4. Verify the rebase changed history, not content: compare the
   branch's diff against its base before and after (`git range-diff`
   or `git diff` of the two three-dot ranges). Unexpected content
   drift halts the run.
5. If conflicts were resolved, run the project's fast quality gates
   — format, lint, typecheck, scoped tests, discovered from its
   AGENTS.md/CLAUDE.md — and fix failures before pushing.
6. Force-push the PR branch, and only that branch, with
   `git push --force-with-lease` — never bare `--force`.
7. Wait for CI on the rebased head: `gh pr checks <n> --watch`.

## Merge commit message

Study the repository's own history before writing the message. Fetch
trunk first so the history is current:

```console
$ git fetch origin <trunk>
```

For a merge-commit strategy, read recent merges:

```console
$ git log --merges -10 --format='%s%n%n%b' origin/<trunk>
```

For `--squash` or `--rebase`, a squash-only repo has no merge commits, so
read the first-parent history instead:

```console
$ git log --first-parent -10 --format='%s%n%n%b' origin/<trunk>
```

Match what is observed — subject shape, whether a `(#N)` suffix is
used, body structure, wrapping. If the repo has no merge history,
fall back to the commit conventions in its AGENTS.md/CLAUDE.md, then
to a plain descriptive subject. Keep the body proportional: a small
fix needs a subject only; a feature gets a short narrative paragraph
and labeled bullets. No `Co-Authored-By`, no "Generated with" or other
tool trailers, no emoji.

Compose `-t <subject> -b <body>` only for `--merge` or `--squash`, and only
when the user passed no `-t`, `-b`, or `--body-file` of their own. With
`--rebase`, or with the user's message flags, pass the user's flags alone.

### Stay provincial

Merging a PR is not cutting a release. Unless the PR itself is
release management (a version bump, a release-notes PR), the merge
commit and any text this command writes must not claim the change
lands "in vX.Y", edit CHANGES/CHANGELOG files, tag, or otherwise
tread into release territory. Describe what the branch ships and
stop there.

## Strategy and flag passthrough

Pin the merge to the head that was verified: after the final CI wait, read
`gh pr view <n> --json headRefOid` and pass `--match-head-commit <sha>`,
unless the user supplied their own. A push after the checks passed then
fails the merge instead of landing unreviewed commits; on that failure,
re-run the gate.

The default strategy is a merge commit (`--merge`). `--squash` and
`--rebase` override it, and every other `gh pr merge` flag the user
supplies passes through verbatim — `--auto`, `--delete-branch`,
`--admin`, `--match-head-commit`, `--author-email`, `--body-file`,
`--repo`, and the rest of `gh pr merge --help`. Do not translate or
second-guess them.

### `--admin` policy

`--admin` bypasses branch protection, nothing more. It is acceptable
when CI is otherwise passing and the only blocker is a protection
rule (for example a required-review rule on a solo repo). It is never
used to merge over failing or pending checks, over a critical error
found during discovery, or over anything that violates the repo's
AGENTS.md/CLAUDE.md. If the user did not pass `--admin` and it turns
out to be needed, ask before using it; without a question tool, halt and
report the blocker.

`--admin` yields to AGENTS.md because it overrides a control the
repository set for everyone, not because repo rules outrank flags in
general. A flag that authorizes a step the user would otherwise run by
hand, such as a release command's tag and push flags, is the user's
decision and stands.

## After each merge

1. Confirm the merge landed (`gh pr view <n> --json state,mergedAt`).
2. If the working tree is dirty, skip the sync and say so. Otherwise
   `git checkout <trunk>` and `git pull` so the local trunk matches
   what was just merged. If the user started on a different branch that
   was not the merged PR's, return to it afterward.
3. Report and stand by — never chain into tagging, releasing, or
   deploying.

The merge itself always goes through `gh pr merge`, never a local
`git merge` pushed to trunk.
