---
name: update-downstream-packages
description: "Use when rolling a newly published package release through every maintained consumer repository and verifying CI."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion", "Task"]
argument-hint: "<package> [<version>] [--roots <glob>...] [--push]"
user-invocable: true
disable-model-invocation: true
---

# Update Downstream Packages

A new release of one of the user's packages is published. Find every repo
of theirs that consumes it, bump the pin (and sibling workspace packages
released with it), refresh lockfiles, commit, optionally push to trunk, and
verify CI end to end.

Arguments: $ARGUMENTS

This command can push to trunk of many repos. Phases 1 and 2 only read;
every cache clean, commit, push, and CI rerun waits for the Phase 3 gate.
Without `--push` it leaves commits local and prints the push command per
repo, and CI verification does not apply.

---

## Phase 1: Inputs and Pre-flight

1. **Package** — the first non-flag argument. If missing, ask.
2. **Version** — the second non-flag argument, or the latest published
   version from the package index (PyPI:
   `https://pypi.org/pypi/<package>/json`; npm: `npm view <package> version`).
   Confirm it exists on the index before touching anything.
3. **Workspace roots** — from `--roots` globs. If not given, ask the user
   which directories hold their checkouts; assume no layout.
4. **Sibling packages** — if the package is developed in a workspace repo
   that publishes several packages versioned together, list the siblings
   (from the source repo's manifests or the index). They bump together.

## Phase 2: Discover Consumers

Scan each workspace root for repos whose manifest depends on the package.
Take the manifest names from the ecosystem the package is published to
(`pyproject.toml` and `package.json` below are one example). Match the whole
package name, so `foo` does not hit `foo-bar`, and escape `.` in the name:

```console
$ rg -l '(^|[^A-Za-z0-9_.-])<package>([^A-Za-z0-9_.-]|$)' \
    --max-depth 2 \
    -g pyproject.toml \
    -g package.json \
    <root>
```

For each hit, record:

- **Worktree?** A `.git` that is a file marks a linked worktree; skip it,
  the primary checkout is found on its own.
- **Trunk** — `git symbolic-ref refs/remotes/origin/HEAD`, falling
  back to whichever of `main`/`master` exists.
- **Owner** — from `git remote get-url origin`. Group repos by owner
  org; the user confirms which orgs are in scope at the gate.
- **Current pin(s)** — the pinned version(s) of the package and any
  siblings in the manifest.
- **Source overrides** — dependency sources that shadow the index (for
  example `[tool.uv.sources]` entries, npm `file:`/`link:`/`git:` specs).
  Remove the override so the published package is used, as its own commit
  before the bump.
- **Resolver cutoffs** — a cooldown setting that hides fresh releases (uv's
  `exclude-newer` is one). Read the tool's current documentation for its
  key names and per-package exemption syntax. If one is set, check that the
  package and every sibling are exempt; a missing entry blocks the fresh
  release at lock time, so add it as its own commit before the bump.
- **Dirty?** Repos with uncommitted changes get reported and skipped
  unless the user says otherwise.

## Phase 3: Confirmation Gate (mandatory)

Present the plan before mutating anything:

- Per repo: path, owner, branch to update, current pin → new version,
  and any prep commits needed (source-override removal, cooldown
  exemption additions).
- Skipped repos with reasons (worktree, dirty, org out of scope).
- Whether pushes will happen (only with `--push`).
- Every mutation outside the working trees: the resolver cache clean, the
  `gh cache delete --all` per pushed repo, and the failed-run `gh run rerun`
  (at most once per run).

Ask the user via `AskUserQuestion` which owner orgs are in scope and
whether any repo needs a branch override or an **additional** long-lived
branch beyond trunk (the user names it; the same per-repo procedure runs on
it). Do not proceed without confirmation. Without `AskUserQuestion` (Codex,
headless runs), print the plan and stop; a request to run the command is not
confirmation of the plan.

## Phase 4: Per-Repo Procedure

Repos are independent: parallelize with background agents batched by owner
org (up to 4 batches), or run sequentially. Each repo, on each of its
confirmed branches:

0. **Fresh resolver cache** — once, after the gate and before the first
   lock, clear the package manager's resolver cache so every lock resolves
   against the newly published files (uv: `uv cache clean --force`, which
   clears a global cache).
1. **Sync** — `git checkout <branch> && git pull --ff-only`.
2. **Prep commits** (each on its own, only if discovery flagged it):
   - Remove the source override so the repo consumes the published
     index package. Commit it alone, in the repo's own commit style.
   - Add missing cooldown exemptions in the tool's documented syntax,
     keeping the file's ordering. Commit alone, with a body noting the
     cooldown would otherwise block the fresh release.
3. **Bump pins** — replace the pinned version for the package and each
   sibling in the manifest, one name at a time, with the project's own
   tooling where it has some. A text edit must anchor on the name and a
   version boundary so `0.1.1` never rewrites `0.1.10`, `0.1.1a1`, or another
   package's pin; escape `.` in the version and name. For `pyproject.toml`
   `==` pins with GNU coreutils:

   ```console
   $ sed -i -E 's/^([[:space:]]*"<name>(\[[^]]*\])?[[:space:]]*==[[:space:]]*)<old-version>([^0-9A-Za-z.+_-]|$)/\1<new-version>\3/' pyproject.toml
   ```

   On BSD/Darwin, `-i` requires an explicit backup suffix, and an
   empty one edits in place:

   ```console
   $ sed -i '' -E 's/^([[:space:]]*"<name>(\[[^]]*\])?[[:space:]]*==[[:space:]]*)<old-version>([^0-9A-Za-z.+_-]|$)/\1<new-version>\3/' pyproject.toml
   ```

   Review `git diff`: only the intended pins changed. For other manifests or
   pin syntax, edit the matching dependency line or use the package
   manager's own install command.

4. **Re-lock** — the ecosystem's lock command (`uv lock`,
   `npm install --package-lock-only`, ...). On a resolution failure,
   clear the resolver cache and retry once.
5. **Prerelease warnings mean stop.** If locking warns about prerelease
   resolution or would need `--prerelease` flags or config to accept the
   version, add none of them; halt this repo and report. The cause is
   upstream: a stale cache, a missing cooldown exemption, or a bad publish.
6. **Gates** — run the repo's own quality checks (from its AGENTS.md /
   CLAUDE.md) when they are quick; on a failure, halt this repo and report.
   A red local gate must not reach trunk.
7. **Commit** — mirror the repo's own previous bump commits for this
   package (`git log --oneline --grep '<package>'`). Fallback subject,
   version-arrow form:

   ```
   <package> <old> → <new>
   ```

   Body: what the new release ships, read from the package's CHANGES
   entry for the version. Write it per
   `../../references/prose-rules.md`. No `Co-Authored-By` line, no
   "Generated with" or other tool trailer, no emoji.
8. **Push** — With `--push`, `git push`; otherwise skip it and print the command
   in the report. Never force.

## Phase 5: Verify with gh

For every pushed repo:

1. Clear stale Actions caches so CI resolves fresh:

   ```console
   $ gh cache delete --all --repo <owner>/<repo>
   ```

2. Find the run for the pushed commit:

   ```console
   $ gh run list --repo <owner>/<repo> --branch <branch> --limit 1
   ```

   Then wait for it to conclude:

   ```console
   $ gh run watch <run-id> --repo <owner>/<repo> --exit-status
   ```

3. On failure: clear the cache again and rerun the failed jobs once
   (`gh run rerun <run-id> --failed`). If it still fails, compare with the
   run before the bump and report a pre-existing failure as such.
4. Where the repo deploys docs from CI, confirm the docs job succeeded too.

## Output

1. Hero line: `✓ <package> <old> → <new> across N repos` (or `⚠` with
   the failure count).
2. `## Rollout summary`: per repo, branch, prep commits, bump commit,
   pushed or local, CI status.
3. `## Stopped repos`: any halted on prerelease warnings, dirty trees, or
   persistent CI failures, each with what the user should look at.
4. Next-step `AskUserQuestion` panel: rerun failed CI checks, retry stopped
   repos, push the local commits, or done. Each choice needs its own
   confirmation of the exact repos. Without `AskUserQuestion`, list the
   options and stop.

A stopped run (missing package, version not on the index, no gate
confirmation) is one result sentence, then what the user needs to do.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
✓ libvcs 0.37.0 → 0.38.0 across 2 repos

## Rollout summary

- vcspull on main: bump commit 4e1a9b2, pushed, CI passed.
- g on main: removed the uv source override (1d7c3f0), bump commit a95e260, kept local.

## Stopped repos

- unihan-etl: dirty working tree; commit or stash its changes, then retry.
```
