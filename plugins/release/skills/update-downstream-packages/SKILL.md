---
name: update-downstream-packages
description: "Use when rolling a newly published package release through every maintained consumer repository and verifying CI."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion", "Agent"]
argument-hint: "<package> [<version>] [--roots <glob>...] [--push]"
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
repo (`git push --no-follow-tags --recurse-submodules=no <remote> <commit>:refs/heads/<branch>`), and CI verification does not apply. It pushes to trunk or a branch
the user names at the gate; opening pull requests is out of scope.

---

## Phase 1: Inputs and Pre-flight

1. **Package**: the first non-flag argument. If missing, ask.
2. **Version**: the second non-flag argument, or the latest published
   version from the package index (PyPI:
   `https://pypi.org/pypi/<package>/json`; npm: `npm view <package> version`;
   crates.io: `https://crates.io/api/v1/crates/<package>`; Go:
   `https://proxy.golang.org/<module>/@latest`).
   Confirm it exists on the index before touching anything, and confirm every
   sibling version the same way (step 4); each check
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
   (from the source repo's manifests or the index). They bump together only
   when each sibling's target version is confirmed on the index. An
   unconfirmed sibling stops the rollout until the user supplies its version
   or removes it from the plan.

## Phase 2: Discover Consumers

Inventory repositories before searching for dependencies. Resolve
`../../scripts/consumer_inventory.py` against this SKILL.md's directory and
write its absolute path literally in each command; resolve `../../scripts/publish.py` and `../../scripts/bump_pin.py` the same way. Resolve the user's root
globs to explicit directories without evaluating shell text; missing or ambiguous
roots need clarification. Never show the helper or local root paths in replies.

```console
$ python3 <absolute-consumer-inventory.py> inventory <root> <other-root> > <new-inventory.json>
```

The helper scans nested and hidden directories without ignore filters. Its JSON
keeps each checkout and its Git/common-directory identities, available refs and
explicit omissions. It never fetches or checks out; exit 1 means incomplete
evidence, 2 means usage failure. Read errors, symlink boundaries, missing metadata
and resource limits must not become "no consumers." Resolve coverage gaps or
report them as outstanding per `../../references/prose-rules.md`; a partial
inventory cannot establish that every maintained consumer was found.

Retain each full JSON result in a fresh run-owned artifact outside every consumer
checkout, including failed or incomplete attempts. Inspect `complete`,
`omissions`, repository/branch identities and the relevant tree or checkout
classifications selectively; decode only the requested inputs needed for review.
Do not print the full tree, index and working records into the conversation.

The byte budget covers Git output, requested blobs and every tracked regular
file read during checkout validation. On a resource-limit omission, retain the
unresolved roots or branch row and the limits used. Review the observed cost
and choose an explicit finite budget for the next invocation; place
`--max-entries`, `--max-bytes` and `--max-seconds` before `inventory` or `snapshot`.
Rerun the incomplete scope with those reviewed bounds and a fresh artifact.
If coverage still cannot be established within the agreed bounds, keep it under
`## Stopped repos`; never drop roots, branches or inputs to obtain completion.

Select trunk and any user-named maintained branches for every candidate repo
before excluding nonconsumers. Ask about additional branches now, not only for
repositories with a current-checkout match. Keep separate repo/branch rows.
Group checkouts by common-directory identity without dropping a distinct branch;
a gitfile primary or an in-scope linked checkout is not a reason to skip.
Do not select an out-of-scope primary in place of the supplied checkout.

Read each full branch ref without switching the checkout:

```console
$ python3 <absolute-consumer-inventory.py> snapshot \
    --repo <checkout> \
    --ref refs/heads/<branch> > <new-snapshot.json>
```

Use the complete recursive tree to find manifest, workspace, lock and gate inputs
for the project's ecosystem, including nested or lockfile-only consumers. Repeat
the snapshot with `--read <tree-path>` for every relevant input; it returns exact
blob identities and base64 bytes. Read referenced gate scripts/configuration too.
Missing refs/objects remain unverified; the helper cannot establish remote
freshness. Resolve every reported gitlink or symlink boundary separately before
claiming coverage. An uninitialized submodule needs its own supplied checkout;
never create one during discovery. A submodule's identity and branch are distinct
from its parent's, and approval does not authorize changing the parent's gitlink.

Use project tooling or inspect actual dependency declarations to establish a
consumer. Whole-file name matches only identify candidates; ambiguous formats
remain unverified. Respect ecosystem name normalization, including PyPI's
case-insensitive equivalence of runs of `-`, `_` and `.`. This helper does not
parse or authorize dependency edits.

For each repo/branch, record:

- **Snapshot**: checkout/Git/common identity, full branch ref, observed commit
  and exact input paths/blob identities. These are local observations.
- **Trunk**: `git symbolic-ref refs/remotes/<remote>/HEAD`, falling
  back to whichever of `main`/`master` exists. `<remote>` is trunk's
  upstream remote (`origin` by default).
- **Owner and push endpoint**: from the helper below. Group repos by the
  owner of the push URL; the user confirms which orgs are in scope at the
  gate. A refusal (several push URLs, credentials in the URL, a rewrite rule,
  a mirror or push-option setting) stops that repo's row.

  ```console
  $ python3 <absolute-publish.py> --repo <checkout> inspect --remote <remote>
  ```
- **Current pin(s)**: that branch's versions of the package and any siblings.
- **Source overrides**: dependency sources that shadow the index (for
  example `[tool.uv.sources]` entries, npm `file:`/`link:`/`git:` specs).
  Remove the override so the published package is used, as its own commit
  before the bump, only when the confirmed plan lists that conversion;
  otherwise leave a deliberately local source and report the row as stopped.
- **Resolver cutoffs**: a cooldown setting that hides fresh releases (uv's
  `exclude-newer` is one). Read the tool's current documentation for its
  key names and per-package exemption syntax. A missing exemption is not
  proof the target is excluded: compare the effective cutoff with the upload
  time of the package and each sibling on the index. Propose an exemption,
  as its own commit before the bump, only when a target is excluded, and
  state in the plan how long it stays and the condition that removes it
  (the release aging past the cutoff). The user approves its duration.
- **Gates**: the repo's own quality checks, from its AGENTS.md / CLAUDE.md.
  Note when none are documented.
- **Checkout state**: for the checked-out branch, repeat the snapshot with
  `--require-checkout` and the relevant `--read` inputs. It compares the selected
  commit with non-converting index records and every tracked regular file's raw
  bytes and executable bit, including files outside `--read`. It reports staged,
  raw-byte/mode, untracked and unsupported states without executing filters.
  Exact byte equality can pass with an applicable identity filter. Transformed
  bytes, sparse entries, symlinks and submodules need separate inspection;
  a refusal cannot establish cleanliness. Never replace this check with status
  or disable filters to obtain a pass. Report and skip changed or unresolved
  rows until their state is handled explicitly.

## Phase 3: Confirmation Gate (mandatory)

Present the plan before mutating anything, per `../../references/prose-rules.md`:

- Per repo/branch: repository label, owner, observed commit, current pin → new version,
  any prep commits needed (source-override removal, cooldown
  exemption additions), and the gates it will run (or that none are
  documented).
- Skipped repos and unresolved coverage, each with its reason. Do not silently
  omit unsearched roots, branches or input formats from the rollout target.
- Whether pushes will happen (only with `--push`), and each repo's push URL
  and destination branch.
- The CI wait budget per repo.
- Every mutation outside the working trees: a resolver cache clean after a
  resolution failure, a `gh cache delete` of exact cache keys that a failed
  run's log shows were restored, and the failed-run `gh run rerun` (at most
  once per repo).

Print the plan in this shape, as plain text with plain bullets and no bold:

```text
Plan: example-pkg 1.4.0 → 1.5.0, pushes on (--push)

- app-one (acme, pushes to git@github.com:acme/app-one.git) on main: pin 1.4.0 → 1.5.0, prep commit removing the uv source override, gates: make test
- app-two (acme, pushes to git@github.com:acme/app-two.git) on main: pin 1.4.0 → 1.5.0, no prep, gates: none documented
- app-two (acme) on release/1.x: pin 1.3.0 → 1.5.0, no prep, gates: make test
- Skipped: app-three (dirty tree), tools-fork (owner outside scope)
- CI wait budget: 20 minutes per repo
- Outside the working trees: uv cache clean example-pkg after a resolution failure, gh cache delete of exact keys a failed run restored, gh run rerun --failed at most once per repo
```

Ask the user via `AskUserQuestion` to confirm owner orgs and the complete
repo/branch plan. A changed or additional branch returns to Discovery for its
own inputs and confirmation; it never inherits another row's pins or gates.
Do not proceed without confirmation. Without `AskUserQuestion` (Codex,
headless runs), print the plan and stop; a request to run the command is not
confirmation of the plan.

## Phase 4: Per-Repo Procedure

Repos are independent: parallelize with background agents batched by owner
org (up to 4 batches), or run sequentially. Each repo, on each of its
confirmed branches:

0. **Sync and revalidate**: check the approved checkout identity and its current
   branch with the helper's `--require-checkout`, then perform the authorized
   checkout and fast-forward sync. Observe branch, HEAD/refs, index and working
   state after each command, even on failure. Stop the row on failure, unreadable
   state or unexpected changes; preserve its observed effects and report per
   `../../references/prose-rules.md`.

   Reread that branch's pins, overrides, resolver settings, lock inputs and gates
   before any cache clean, prep change, pin edit or lock step. Re-run its snapshot
   with every approved `--read` input plus `--expect-commit <approved-oid>` and
   `--require-checkout`. Raw equality is narrower than project-normalized Git
   cleanliness: content transformations remain unresolved, never silently
   normalized, bypassed or repaired. Resolve every reported coverage limit.

   If sync changed the commit, inputs or proposed work, present the revised row
   and obtain fresh approval; headless runs stop. Rediscover added or removed
   inputs rather than relying on the old list. Preserve the synchronized state
   without reset/stash. An unchanged row can proceed. After any approval, repeat
   the check immediately before execution; observations do not lock out writers.
1. **Revalidate every additional branch independently** before touching it.
2. **Prep commits** (each on its own, only if discovery flagged it and the plan
   approved it). They precede the gates and stay local if a later step fails:
   report their ids under `## Stopped repos`. To resume, list the local commits
   ahead of the remote and skip a prep commit only when it already holds the
   approved change; never reset or amend to retry.
   - Remove the source override so the repo consumes the published
     index package. Commit it alone, in the repo's own commit style.
   - Add the approved cooldown exemptions in the tool's documented syntax,
     keeping the file's ordering. Commit alone, with a body naming the
     condition that removes them.
3. **Bump pins**: replace the pinned version for the package and each
   sibling in the manifest, one name at a time, with the project's own
   tooling where it has some. A text edit must anchor on the name and a
   version boundary so `0.1.1` never rewrites `0.1.10`, `0.1.1a1`, or another
   package's pin. For `pyproject.toml`, requirements files, and
   `package.json`, run the bundled script once per name. It edits only
   dependency declarations: strings in the `pyproject.toml` dependency arrays,
   requirements lines outside comments and options, and the
   `package.json` dependency sections. It matches the name
   case-insensitively with `-`, `_`, and `.` interchangeable, handles pins
   inside arrays and extras, and rewrites only an exact `==`
   version (`package.json`: the quoted version, with an optional `^` or `~`).
   Any other manifest or syntax it cannot read unambiguously is refused (exit
   3); edit those with the project's own tooling after approval.
   Resolve `../../scripts/bump_pin.py` against the directory of this SKILL.md
   (the path it was read from) and write that absolute path literally in the
   command; shell variables do not persist between Bash calls. Never show
   that path in the reply:

   ```console
   $ python3 ../../scripts/bump_pin.py pyproject.toml <name> <old-version> <new-version>
   ```

   Exit 0 prints the count of pins changed. Exit 1 means no pin matched and
   no write was attempted. Only on exit 1, if the dependency uses a `>=` or
   `~=` floor, ask whether to raise it; edit it by hand or use the package
   manager's own install command only after approval. Exit 2 is a usage
   error; exit 3 is a file refusal, access, decode or write failure. On either
   error or any unexpected status, stop this repo and report the failure per
   `../../references/prose-rules.md`, without retrying or editing by another
   method. A write failure may leave
   partial content: do not call the file untouched. Ask the user to inspect
   it before any further action. Review successful edits with `git diff`:
   only the intended pins should have changed.

   The helper refuses pre-existing leaf symlinks, hardlinks, non-regular
   entries and files it would change the owner of, writes through a temporary
   file and renames it only if the file is unchanged, and keeps every other
   byte and the file mode. It does not guard parent aliases or a writer that
   wins the final check-to-rename window.

4. **Re-lock**: the ecosystem's lock command (`uv lock`,
   `npm install --package-lock-only`, ...). On a resolution failure,
   clear the resolver cache and retry once.
   Then read the lock diff: the package and each sibling must resolve to the
   new version from the index, not from a source override. A registry check
   does not prove that.
5. **Prerelease warnings mean stop.** If locking warns about prerelease
   resolution or would need `--prerelease` flags or config to accept the
   version, add none of them; halt this repo and report the observed
   diagnostic with its cause unverified. Candidates include a stale cache, a
   cooldown, the resolver's prerelease policy or constraints, and the publish.
6. **Gates**: before any push, run the repo's own quality checks (from
   its AGENTS.md / CLAUDE.md), as the plan listed them. On a failure, halt this repo and report. A red local gate must
   not reach trunk. Parallel agents run exactly the scope the plan names.
   After the last gate passes, record `<pre-commit>` (the current HEAD) and
   the gated bytes:

   ```console
   $ python3 <absolute-publish.py> --repo <checkout> worktree-tree
   ```
7. **Commit**: mirror the repo's own previous bump commits for this
   package (`git log --oneline --grep '<package>'`). Fallback subject,
   version-arrow form:

   ```
   <package> <old> → <new>
   ```

   Body: what the new release ships, read from the package's CHANGES
   entry for the version. Write it per
   `../../references/prose-rules.md`. No `Co-Authored-By` line, no
   "Generated with" or other tool trailer, no emoji.

   Then verify that the commit is the one new commit on `<pre-commit>` with the
   gated bytes, and record its `commit`. A hook that changed committed bytes
   (`tree-differs`) needs the gates rerun against the committed tree, as in
   `../cut/SKILL.md` Phase 5; stop the repo if they fail.

   ```console
   $ python3 <absolute-publish.py> --repo <checkout> verify-commit \
       --parent <pre-commit> \
       --tree <gated-tree> \
       --branch <branch>
   ```

8. **Push**: With `--push`, push the verified `commit` to the plan's push URL
   and read the remote branch back; otherwise skip it and print the command
   in the report. Never force, never run a raw `git push`. Exit 3 (rejected,
   hook or protected trunk) or 4 (unverified) halts this repo: report it as
   stopped, never as pushed, and skip Phase 5 for it.

   ```console
   $ python3 <absolute-publish.py> --repo <checkout> push-branch \
       --remote <remote> \
       --branch <branch> \
       --commit <commit> \
       --approved-url <push-url>
   ```

## Phase 5: Verify with gh

For every pushed repo, bind each `gh` call to the plan's host, owner and
repository with `--repo [HOST/]OWNER/REPO`, and to the pushed commit.

1. List every run for the pushed commit, with its workflow, event, attempt and
   conclusion:

   ```console
   $ gh run list \
       --repo <owner>/<repo> \
       --commit <pushed-sha> \
       --limit 100 \
       --json databaseId,workflowName,event,attempt,status,conclusion
   ```

   The expected set is every workflow of the pushed commit that triggers on a
   push to the branch (read from its workflow files), plus the required checks
   the host reports for the commit. If a workflow has no run after a few tries,
   or the expected set cannot be established, report CI as unconfirmed. One
   green run does not cover the others. A run for an older commit is not this one.

2. Wait for each pending run within the plan's CI wait budget, in the
   background, and stop waiting when the budget ends. Pending at the deadline
   is reported as pending, never passed:

   ```console
   $ gh run watch <run-id> \
       --repo <owner>/<repo> \
       --exit-status
   ```

3. CI passes only when every expected workflow and required check concluded
   successfully for the pushed commit.
4. On failure, read the failed job's log. Delete a dependency cache only when
   the log shows it restored a stale cache; delete those exact keys, listed
   with `gh cache list --repo <owner>/<repo>`, never `--all`, then rerun once:

   ```console
   $ gh run rerun <run-id> \
       --repo <owner>/<repo> \
       --failed
   ```

   If it still fails, call the failure pre-existing only when the same job
   failed with a matching error on the run for the parent commit; otherwise
   report its cause as unknown.
5. Where the repo deploys docs from CI, the docs job is part of the expected set.

## Output

Write the report per `../../references/prose-rules.md` in this order:

1. Hero line: when discovery coverage is complete,
   `✓ <package> <old> → <new> across N repos`, or
   `⚠ <package> <old> → <new>: K of N repos stopped` when any repo stopped.
   Example: `⚠ libvcs 0.37.0 → 0.38.0: 1 of 3 repos stopped`.
   When roots, maintained branches or input formats remain unverified, use
   `⚠ <package> <old> → <new>: partial rollout; consumer total unverified`.
   Do not invent a denominator from the discovered subset.
2. `## Rollout summary`: per repo, branch, prep commits, bump commit,
   pushed (read back) or local, CI status (passed, failed, pending at the
   budget, or unconfirmed).
3. `## Stopped repos`: any halted on prerelease warnings, dirty trees, rejected pushes, or
   persistent CI failures, each with what the user should look at and the
   ids of any local prep commits it left.
   Include unresolved roots, maintained branches, input formats and exhausted
   resource bounds here, even when their consumer repositories are unknown.
   Give each a label, the coverage gap and the action needed to resolve it.
4. Next-step `AskUserQuestion` panel: resolve discovery gaps, rerun failed CI
   checks, retry stopped repos, push the local commits, or done. Each choice needs its own
   confirmation of the exact repos. Without `AskUserQuestion`, list the
   options and stop.

A run that stops before the plan (missing package, version not on the index,
an unconfirmed sibling, no roots) is one result sentence, then what the user
needs to do. A headless run that reaches the plan prints the plan and stops.
Name
the unconfirmed precondition and what the user supplies, never the sandbox
or network environment. No promise of what happens next.

Reply to a stop in this shape, with the same formatting rules:

```text
Stopped: example-pkg 2.0.0 is not confirmed on its package index, so nothing was changed.

- Confirm the version is published and which index (PyPI, npm, crates.io, or Go) holds it.
- Pass your checkout directories with --roots, and --push if you want the commits pushed.
```

A CI failure is a stop for that repo: name the repo, the failed job, and
whether the same job failed before the bump or that is unknown, as a bullet under
`## Stopped repos`. Do not paste log output. For example:

```text
- vcspull on main: job "tests (3.12)" failed after the bump and passed on the previous run; inspect the bump commit.
```

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ libvcs 0.37.0 → 0.38.0: 1 of 3 repos stopped

## Rollout summary

- vcspull on main: bump commit 4e1a9b2, pushed and read back, CI passed.
- g on main: removed the uv source override (1d7c3f0), bump commit a95e260, kept local.

## Stopped repos

- unihan-etl: dirty working tree; commit or stash its changes, then retry.
```
