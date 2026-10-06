# Worktree setup and exit

The per-unit steps the `action-worktree` skill runs in its own turn and
this skill runs for each unit in its main loop.

## Situational awareness

1. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for
   quality checks, commit format, and any branch-naming conventions
   (these feed rung 2 of the ladder).
2. Resolve the five gate buckets and the CI-coverage split.
3. Inventory ticket tooling: tracker MCP tools, the `gh` CLI. Detect
   the trunk branch and remotes (`git remote -v`,
   `git symbolic-ref refs/remotes/origin/HEAD`).
4. Record main-checkout state (`git status -sb`). A dirty main tree
   is not a blocker, because the worktree isolates the work. Note it,
   and never stash or otherwise touch the user's uncommitted work.

## Worktree and branch

Start point: the remote trunk head (`git fetch origin`, then
`origin/<trunk>`), falling back to the local trunk, then `HEAD`. The
plan states which; a fallback may be stale.

Resolve **idempotently**, first match wins. Collision checks come
before any attach or create:

1. **Branch checked out in a linked worktree.** The first entry of
   `git worktree list --porcelain` is the main checkout; every later
   entry is a linked worktree. If a linked entry holds the branch, its
   path wins even when it differs from the computed target.
   **Resume**: inspect its state (`git -C <path> status --short`,
   commits ahead of the start point) and continue from the first
   incomplete step: uncommitted changes, resume implementation; green
   commits present, continue to the exit axis; primer only, start
   implementation
   (or report a no-op under `--setup-only`). Report "resumed", not
   "created".
2. **Branch checked out in the main checkout.** Not a resume: the work
   would not be isolated. Ask for another branch name or abort.
   Non-interactive: report `⚠ blocked at worktree setup`, change nothing.
3. **Directory collision.** The computed path exists on disk but is
   not a worktree of this branch (unregistered directory, or
   registered to a different branch). Ask with `ask-user-choice`:
   another path, the user clears it, or abort. Non-interactive:
   report `⚠ blocked at worktree setup`, change nothing. Never delete or
   overwrite a directory this command did not create.
4. **Branch exists, no worktree.** Attach one:

```console
$ git worktree add <path> <branch>
```

5. **Fresh.** Create both:

```console
$ git worktree add -b <branch> <path> <start-point>
```

Then assemble the **ticket primer** — per ticket: ID, title,
description, acceptance criteria, link. The primer lives in this
command's report (`## Primer`), not in files inside the worktree: an
untracked primer file would show in `git status` and could ride into
a commit. With `--setup-only`, skip ahead to the output contract now.

## Exit axis

- **Default:** stop after the gated commit(s). No push; the branch
  and worktree stay local for the user.
- **`--push`:** publish with an upstream:

```console
$ git push -u origin <branch>
```

- **`--pr`:** push as above, then open the PR with the tickets
  linked per ticket-detection.md § Server-side linking: GitHub
  closing keywords (`Fixes #123`) in the body; Linear IDs already in
  the branch name and repeated in the PR title for auto-attach:

```console
$ gh pr create --title "<title>" --body "<body linking the tickets>"
```

  On non-GitHub forges use the forge's CLI equivalent when present;
  otherwise report the prepared title and body for manual creation.
  After opening, offer `gh pr checks --watch` when CI is observable.
