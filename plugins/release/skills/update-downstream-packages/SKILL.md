---
name: update-downstream-packages
description: "Use when rolling a newly published package release through every maintained consumer repository and verifying CI."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion", "Task"]
argument-hint: "<package> [<version>] [--roots <glob>...] [--push]"
user-invocable: true
disable-model-invocation: true
---

# Update Downstream Packages

A new release of one of the user's packages is published. Find every
repo of theirs that consumes it, bump the pin (and sibling workspace
packages released together with it), refresh lockfiles, commit, optionally
push to trunk, and verify CI end to end.

Arguments: $ARGUMENTS

This command can push to trunk of many repos. Nothing is mutated
before the Phase 3 confirmation gate: Phases 1 and 2 only read, and
every cache clean, commit, push, and CI rerun waits for the gate.
Without `--push` it leaves commits local and prints the push command per
repo; CI verification then does not apply.

---

## Phase 1: Inputs and Pre-flight

1. **Package** — the first non-flag argument. If missing, ask.
2. **Version** — the second non-flag argument, or discover the latest
   published version from the package index (for PyPI:
   `https://pypi.org/pypi/<package>/json`; for npm:
   `npm view <package> version`). Confirm the version exists on the
   index before touching anything.
3. **Workspace roots** — from `--roots` globs. If not given, ask the
   user which directories hold their open-source checkouts (e.g.
   glob patterns two levels deep under a work directory). Do not
   assume a layout.
4. **Sibling packages** — if the package is developed in a workspace
   repo that publishes several packages versioned together, list the
   siblings (from the source repo's `packages/*` manifests or the
   index). They bump together.

## Phase 2: Discover Consumers

Scan the workspace roots for repos whose manifest depends on the
package:

Match the whole package name, so `foo` does not hit `foo-bar`. Escape
`.` in the name:

```console
$ rg -l '(^|[^A-Za-z0-9_.-])<package>([^A-Za-z0-9_.-]|$)' <root>/*/pyproject.toml <root>/*/package.json
```

For each hit, record:

- **Worktree?** If `.git` is a file rather than a directory, it is a
  linked worktree — skip it; the primary checkout will be found on
  its own.
- **Trunk** — `git symbolic-ref refs/remotes/origin/HEAD`, falling
  back to whichever of `main`/`master` exists.
- **Owner** — from `git remote get-url origin`. Group repos by owner
  org; the user confirms which orgs are in scope at the gate.
- **Current pin(s)** — the pinned version(s) of the package and any
  siblings in the manifest.
- **Source overrides** — dependency sources that shadow the index
  (for example `[tool.uv.sources]` entries, npm `file:`/`link:`/`git:`
  specs).
  These repos need the override removed and the published index
  package used instead — as its own commit, before the bump.
- **Resolver cutoffs** — a cooldown setting that hides fresh releases
  (uv's `exclude-newer` is one). Read the tool's current documentation
  for its key names and per-package exemption syntax before relying on
  them. If one is set, check that the package and every sibling are
  exempt. A missing entry blocks the fresh release at lock time; add it
  as its own commit, before the bump.
- **Dirty?** Repos with uncommitted changes get reported and skipped
  unless the user says otherwise.

## Phase 3: Confirmation Gate (mandatory)

Present the plan before mutating anything:

- Per repo: path, owner, branch to update, current pin → new version,
  and any prep commits needed (source-override removal, cooldown
  exemption additions).
- Skipped repos with reasons (worktree, dirty, org out of scope).
- Whether pushes will happen (only with `--push`).
- Every mutation outside the repos' working trees: the resolver cache
  clean, the `gh cache delete --all` per pushed repo, and the failed-run
  `gh run rerun` (at most once per run).

Ask the user to confirm scope via `AskUserQuestion` — which owner
orgs are in scope, and whether any repo needs a branch override or an
**additional** branch beyond trunk (some projects maintain a
long-lived second branch that also consumes the package; the user
names it, the same per-repo procedure runs on it). Do not proceed
without confirmation. Without `AskUserQuestion` (Codex, headless runs),
print the plan and stop; a request to run the command is not
confirmation of the plan.

## Phase 4: Per-Repo Procedure

Repos are independent — parallelize with background agents batched by
owner org (up to 4 batches), or run sequentially if agents are
unavailable. Each repo, on each of its confirmed branches:

0. **Fresh resolver cache** — once, after the gate and before the first
   lock, clear the package manager's resolver cache so every lock
   resolves against the newly published files (for uv:
   `uv cache clean --force`; it clears a global cache).
1. **Sync** — `git checkout <branch> && git pull --ff-only`.
2. **Prep commits** (each on its own, only if discovery flagged it):
   - Remove the source override so the repo consumes the published
     index package. Commit it alone, in the repo's own commit style.
   - Add missing cooldown exemptions in the tool's documented syntax,
     keeping the file's ordering. Commit alone, with a body noting the
     cooldown would otherwise block the fresh release.
3. **Bump pins** — replace the pinned version for the package and each
   sibling in the manifest, one name at a time. Anchor on the name and
   a version boundary so `0.1.1` never rewrites `0.1.10`, `0.1.1a1`, or
   another package's pin; escape `.` in the version and name. With GNU
   coreutils, for `pyproject.toml` `==` pins:

   ```console
   $ sed -i -E 's/^([[:space:]]*"<name>(\[[^]]*\])?[[:space:]]*==[[:space:]]*)<old-version>([^0-9A-Za-z.+_-]|$)/\1<new-version>\3/' pyproject.toml
   ```

   On BSD/Darwin, `-i` requires an explicit backup suffix, and an
   empty one edits in place:

   ```console
   $ sed -i '' -E 's/^([[:space:]]*"<name>(\[[^]]*\])?[[:space:]]*==[[:space:]]*)<old-version>([^0-9A-Za-z.+_-]|$)/\1<new-version>\3/' pyproject.toml
   ```

   Review `git diff`: only the intended pins changed. For `package.json`
   or other pin syntax, edit the matching dependency line or use the
   package manager's own install command.

4. **Re-lock** — the ecosystem's lock command (`uv lock`,
   `npm install --package-lock-only`, ...). On a resolution failure,
   clear the resolver cache and retry once.
5. **Prerelease warnings mean stop.** If locking warns about
   prerelease resolution or would need `--prerelease` flags or
   config to accept the version, do not add flags, pins, or config
   to force it through; halt this repo and report. A warning means
   something upstream is wrong: a stale cache, a missing cooldown
   exemption, or a bad publish.
6. **Gates** — run the repo's own quality checks (from its AGENTS.md /
   CLAUDE.md) when they are quick; on a failure, halt this repo and
   report. CI verifies afterwards, but a red local gate must not reach
   trunk.
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
   (`gh run rerun <run-id> --failed`). If it still fails, compare with
   the run before the bump — a pre-existing failure is reported as
   such, not retried forever.
4. Where the repo deploys docs from CI, confirm the docs job/workflow
   succeeded too — a docs-dependency bump that breaks the docs build
   defeats the point.

## Output

1. Hero line: `✓ <package> <old> → <new> across N repos` (or `⚠` with
   the failure count).
2. **Rollout summary** — per repo: branch, prep commits, bump commit,
   pushed or local, CI status.
3. **Stopped repos** — any halted on prerelease warnings, dirty
   trees, or persistent CI failures, each with what the user should
   look at.
4. Next-step `AskUserQuestion` panel: rerun failed CI checks / retry
   stopped repos / push the local commits / done. Each choice
   needs its own confirmation of the exact repos. Without
   `AskUserQuestion`, list the options and stop.

A stopped run (missing package, version not on the index, no gate
confirmation) is one result sentence, then what the user needs to do.
