---
name: release-update-downstream-packages
description: >-
  Use when rolling a newly published package release through every
  maintained consumer repository and verifying CI.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion", "Agent"]
metadata:
  argument-hint: "<package> [<version>] [--roots <glob>...] [--push]"
  source: "plugins/release/skills/update-downstream-packages/SKILL.md"
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
repo, and CI verification does not apply. It pushes to trunk or a branch
the user names at the gate; opening pull requests is out of scope.

---

## Phase 1: Inputs and Pre-flight

1. **Package**: the first non-flag argument. If missing, ask.
2. **Version**: the second non-flag argument, or the latest published
   version from the package index (PyPI:
   `https://pypi.org/pypi/<package>/json`; npm: `npm view <package> version`;
   crates.io: `https://crates.io/api/v1/crates/<package>`; Go:
   `https://proxy.golang.org/<module>/@latest`).
   Confirm it exists on the index before touching anything; each check
   returns 200 or prints the version when it exists, and 404 otherwise:

   - PyPI: `https://pypi.org/pypi/<package>/<version>/json`
   - npm: `npm view <package>@<version> version`
   - crates.io: `https://crates.io/api/v1/crates/<package>/<version>`,
     sent with a `User-Agent` header (the API rejects requests without one)
   - Go: `https://proxy.golang.org/<module>/@v/<version>.info`, with the
     version's `v` prefix and each uppercase letter in the module path
     replaced by one exclamation mark followed by its lowercase (`BurntSushi`
     gets two exclamation marks in total)

   For any other ecosystem, or if a check cannot run, stop and say what
   could not be confirmed and what the user must supply; do not describe
   the environment.
3. **Workspace roots**: from `--roots` globs. If not given, ask the user
   which directories hold their checkouts; assume no layout.
4. **Sibling packages**: if the package is developed in a workspace repo
   that publishes several packages versioned together, list the siblings
   (from the source repo's manifests or the index). They bump together.

## Phase 2: Discover Consumers

Scan each workspace root for repos whose manifest depends on the package.
Take the manifest names from the ecosystem the package is published to
(`pyproject.toml` and `package.json` below are one example; add
requirements files, `Cargo.toml`, `go.mod`, and lockfile-only consumers where
the ecosystem uses them). Match the whole
package name, so `foo` does not hit `foo-bar`. PyPI treats runs of `-`, `_`,
and `.` as one separator and ignores case (PEP 503), so for a PyPI package
lowercase the name, split it on those separators, and rejoin the parts with
`[-_.]+` and match case-insensitively: `Foo.Bar` becomes `foo[-_.]+bar`.
For other ecosystems match the name exactly, escaping `.`:

```console
$ rg -i -l '(^|[^A-Za-z0-9_.-])foo[-_.]+bar([^A-Za-z0-9_.-]|$)' \
    --max-depth 2 \
    -g pyproject.toml \
    -g package.json \
    -g requirements*.txt \
    <root>
```

For each hit, record:

- **Worktree?** A `.git` that is a file marks a linked worktree; skip it,
  the primary checkout is found on its own.
- **Trunk**: `git symbolic-ref refs/remotes/<remote>/HEAD`, falling
  back to whichever of `main`/`master` exists. `<remote>` is trunk's
  upstream remote (`origin` by default).
- **Owner**: from `git remote get-url <remote>`. Group repos by owner
  org; the user confirms which orgs are in scope at the gate.
- **Current pin(s)**: the pinned version(s) of the package and any
  siblings in the manifest.
- **Source overrides**: dependency sources that shadow the index (for
  example `[tool.uv.sources]` entries, npm `file:`/`link:`/`git:` specs).
  Remove the override so the published package is used, as its own commit
  before the bump.
- **Resolver cutoffs**: a cooldown setting that hides fresh releases (uv's
  `exclude-newer` is one). Read the tool's current documentation for its
  key names and per-package exemption syntax. If one is set, check that the
  package and every sibling are exempt; a missing entry blocks the fresh
  release at lock time, so add it as its own commit before the bump.
- **Gates**: the repo's own quality checks, from its AGENTS.md / CLAUDE.md.
  Note when none are documented.
- **Dirty?** Repos with uncommitted changes get reported and skipped
  unless the user says otherwise.

## Phase 3: Confirmation Gate (mandatory)

Present the plan before mutating anything:

- Per repo: path, owner, branch to update, current pin → new version,
  any prep commits needed (source-override removal, cooldown
  exemption additions), and the gates it will run (or that none are
  documented).
- Skipped repos with reasons (worktree, dirty, org out of scope).
- Whether pushes will happen (only with `--push`).
- Every mutation outside the working trees: the resolver cache clean, the
  per-key `gh cache delete` of that repo's dependency caches, and the failed-run `gh run rerun`
  (at most once per run).

Print the plan in this shape, as plain text with plain bullets and no bold:

```text
Plan: example-pkg 1.4.0 → 1.5.0, pushes on (--push)

- app-one (acme) on main: pin 1.4.0 → 1.5.0, prep commit removing the uv source override, gates: make test
- app-two (acme) on main and release/1.x: pin 1.4.0 → 1.5.0, no prep, gates: none documented
- Skipped: app-three (dirty tree), tools-fork (owner outside scope)
- Outside the working trees: uv cache clean example-pkg, gh cache delete per dependency-cache key in each pushed repo, gh run rerun --failed at most once per run
```

Ask the user via `ask-user-choice` which owner orgs are in scope and
whether any repo needs a branch override or an **additional** long-lived
branch beyond trunk (the user names it; the same per-repo procedure runs on
it). Do not proceed without confirmation. Without `ask-user-choice` (Codex,
headless runs), print the plan and stop; a request to run the command is not
confirmation of the plan.

## Phase 4: Per-Repo Procedure

Repos are independent: parallelize with background agents batched by owner
org (up to 4 batches), or run sequentially. Each repo, on each of its
confirmed branches:

0. **Fresh resolver cache**: once, after the gate and before the first
   lock, clear the package manager's resolver cache so every lock resolves
   against the newly published files (uv: `uv cache clean <package>`, once per
   package and sibling).
1. **Sync**: `git checkout <branch> && git pull --ff-only`.
2. **Prep commits** (each on its own, only if discovery flagged it):
   - Remove the source override so the repo consumes the published
     index package. Commit it alone, in the repo's own commit style.
   - Add missing cooldown exemptions in the tool's documented syntax,
     keeping the file's ordering. Commit alone, with a body noting the
     cooldown would otherwise block the fresh release.
3. **Bump pins**: replace the pinned version for the package and each
   sibling in the manifest, one name at a time, with the project's own
   tooling where it has some. A text edit must anchor on the name and a
   version boundary so `0.1.1` never rewrites `0.1.10`, `0.1.1a1`, or another
   package's pin. For `pyproject.toml`, requirements files, and
   `package.json`, run the bundled script once per name. It matches the name
   case-insensitively with `-`, `_`, and `.` interchangeable, handles pins
   inside one-line arrays and extras, and rewrites only an exact `==`
   version (`package.json`: the quoted version, with an optional `^` or `~`).
   Resolve `references/bump_pin.py` against the directory of this SKILL.md
   (the path it was read from) and write that absolute path literally in the
   command; shell variables do not persist between Bash calls. Never show
   that path in the reply:

   ```console
   $ python3 references/bump_pin.py pyproject.toml <name> <old-version> <new-version>
   ```

   It prints the count of pins changed. A non-zero exit means no pin matched
   and the file is untouched. A `>=` or `~=` floor is such a case: ask the
   user whether to raise the floor to the new version, then edit the line
   by hand or use the package manager's own install command. Review `git diff`: only the
   intended pins changed.

4. **Re-lock**: the ecosystem's lock command (`uv lock`,
   `npm install --package-lock-only`, ...). On a resolution failure,
   clear the resolver cache and retry once.
5. **Prerelease warnings mean stop.** If locking warns about prerelease
   resolution or would need `--prerelease` flags or config to accept the
   version, add none of them; halt this repo and report. The cause is
   upstream: a stale cache, a missing cooldown exemption, or a bad publish.
6. **Gates**: before any push, run the repo's own quality checks (from
   its AGENTS.md / CLAUDE.md), as the plan listed them. On a failure, halt this repo and report. A red local gate must
   not reach trunk. Parallel agents run exactly the scope the plan names.
7. **Commit**: mirror the repo's own previous bump commits for this
   package (`git log --oneline --grep '<package>'`). Fallback subject,
   version-arrow form:

   ```
   <package> <old> → <new>
   ```

   Body: what the new release ships, read from the package's CHANGES
   entry for the version. Write it per
   `references/prose-rules.md`. No `Co-Authored-By` line, no
   "Generated with" or other tool trailer, no emoji.
8. **Push**: With `--push`, `git push --no-follow-tags`; otherwise skip it
   and print the command in the report. Never force. A rejected push
   (protected trunk, non-fast-forward) halts this repo: report it as
   stopped, never as pushed, and skip Phase 5 for it.

## Phase 5: Verify with gh

For every pushed repo:

1. Clear stale dependency caches so CI resolves fresh. List the caches, then
   delete each dependency-cache key (never `--all`, which also drops unrelated
   build caches):

   ```console
   $ gh cache list --repo <owner>/<repo>
   ```

   ```console
   $ gh cache delete <key> --repo <owner>/<repo>
   ```

2. Find the run for the pushed commit. Retry up to 5 times, a few seconds
   apart; if no run appears, report CI as unconfirmed for this repo. A run
   for an older commit is not this one:

   ```console
   $ gh run list --repo <owner>/<repo> --branch <branch> --commit <pushed-sha> --limit 1
   ```

   Then wait for it to conclude:

   ```console
   $ gh run watch <run-id> --repo <owner>/<repo> --exit-status
   ```

3. On failure: clear the dependency caches again and rerun the failed jobs once
   (`gh run rerun <run-id> --failed`). If it still fails, compare with the
   run before the bump and report a pre-existing failure as such.
4. Where the repo deploys docs from CI, confirm the docs job succeeded too.

## Output

1. Hero line: `✓ <package> <old> → <new> across N repos`, or
   `⚠ <package> <old> → <new>: K of N repos stopped` when any repo stopped.
   Example: `⚠ libvcs 0.37.0 → 0.38.0: 1 of 3 repos stopped`.
2. `## Rollout summary`: per repo, branch, prep commits, bump commit,
   pushed or local, CI status.
3. `## Stopped repos`: any halted on prerelease warnings, dirty trees, rejected pushes, or
   persistent CI failures, each with what the user should look at.
4. Next-step `ask-user-choice` panel: rerun failed CI checks, retry stopped
   repos, push the local commits, or done. Each choice needs its own
   confirmation of the exact repos. Without `ask-user-choice`, list the
   options and stop.

A stopped run (missing package, version not on the index, no gate
confirmation, CI failure) is one result sentence, then what the user needs to do. Name
the unconfirmed precondition and what the user supplies, never the sandbox
or network environment. No promise of what happens next.

Reply to a stop in this shape, with the same formatting rules:

```text
Stopped: example-pkg 2.0.0 is not confirmed on its package index, so nothing was changed.

- Confirm the version is published and which index (PyPI, npm, crates.io, or Go) holds it.
- Pass your checkout directories with --roots, and --push if you want the commits pushed.
```

A CI failure is a stop for that repo: name the repo, the failed job, and
whether the same job failed before the bump, as a bullet under
`## Stopped repos`. Do not paste log output. For example:

```text
- vcspull on main: job "tests (3.12)" failed after the bump and passed on the previous run; inspect the bump commit.
```

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ libvcs 0.37.0 → 0.38.0 across 2 repos

## Rollout summary

- vcspull on main: bump commit 4e1a9b2, pushed, CI passed.
- g on main: removed the uv source override (1d7c3f0), bump commit a95e260, kept local.

## Stopped repos

- unihan-etl: dirty working tree; commit or stash its changes, then retry.
```


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
