---
name: deslop
description: "Use when cleaning AI slop, verbose commit messages, brittle references, or low-value changes from a branch before review."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
argument-hint: "[<commit-range>] [--apply-patches] [--apply-rebase] [--budget=strict|default|lax] [--targets=diff,messages,both] [--message-only | --diff-only] [--since=<ref>] [--force-rewrite-pushed] [--run-tests] [--no-semantic] [--taxonomy=<path>]"
user-invocable: true
disable-model-invocation: true
---

# `/slop:deslop`

Branch-scoped slop cleaner. Audits every commit on the current branch
since trunk for AI slop, verbose code and comments, fragile hard-coded
references, and low-value contributions. The default run writes a
numbered patch series under `<run-dir>/` with a
checkpointed `apply.sh` and changes nothing else. With `--apply-rebase`,
it also builds fixup commits and runs `git rebase -i --autosquash`.

Invoked by name only: history rewrites must be user-explicit, never
router-inferred. For repo-wide cleanup of files already on trunk, use
`/slop:scan`. The PR description is out of scope; never edit it.

The skill refuses a pushed branch without `--force-rewrite-pushed`, and
refuses `--apply-rebase` when the branch holds merge commits, because
`git rebase -i --autosquash` without `--rebase-merges` flattens topology.

Slop is a workflow label, not proof the text is wrong; reduce
review-hostile noise and leave the author's voice alone. Flag
branch-internal narrative (renames of unshipped symbols, intermediate
states, `### Fixes` for bugs no release had) only when no user of the
latest published release experienced the old name, behavior, or bug.

## `$ARGUMENTS` contract

An empty `$ARGUMENTS` audits `<trunk>..HEAD`. A non-flag token is a
commit range (`<sha>..<sha>` or a single SHA) that overrides it.

| Flag | Default | Effect |
|---|---|---|
| `--apply-patches` | off | Offer "Apply patches now" at the Step 9 gate: fixup commits on `HEAD`, no rebase. Without an apply flag the run stops after writing the patch series. |
| `--apply-rebase` | off | Also offer "Apply and autosquash" at the gate. **Destructive.** Superset of `--apply-patches`. Needs `--force-rewrite-pushed` on a pushed branch, no merge commits in range, and a `--since` ref that is an ancestor of `HEAD`. |
| `--budget=<level>` | `default` | Tier ceiling; table in `../../references/detect-pipeline.md` § Budget and confirmation. |
| `--targets=<list>` | `both` | `diff`, `messages`, or `both`. |
| `--message-only` | off | Shorthand for `--targets=messages`. Exclusive with `--diff-only` and `--targets`. |
| `--diff-only` | off | Shorthand for `--targets=diff`. Exclusive with `--message-only` and `--targets`. |
| `--since=<ref>` | merge-base with trunk | Replaces the trunk merge-base as `BASELINE_SHA`. |
| `--force-rewrite-pushed` | off | Allow a branch that was already pushed. |
| `--run-tests` | off | Include the test command in conflict-loop gates and final verification. |
| `--no-semantic` | off | Skip the Pass B verifier; regex only. |
| `--taxonomy=<path>` | built-in + `.claude/slop.local.yml` | Replace the registry; the built-in set and the override are both ignored. |

## Orchestration Plan

Follow `../../references/detect-pipeline.md` § Orchestration plan. The
plan contains:

1. The trunk ref, `BASELINE_SHA`, and the commit count to scan.
2. The active `--budget` and `--targets`.
3. Quality-gate commands per bucket: `set`, `unset`, or `prompt-user`.
4. The mode: `audit`, `--apply-patches`, or `--apply-rebase`.
5. The branch topology: `local-only`, `pushed`, or `contains-merge-commits`.
6. A findings summary as ranges.

## Step 1: Lock the baseline and snapshot the branch

Fetch first so `origin/<trunk>` and the upstream are current. An offline
failure is not fatal: continue and note in the report that the
comparison may be stale.

```console
$ git fetch origin
```

Resolve `BASELINE_SHA` per `../../references/detect-pipeline.md` §
Baseline; `--since=<ref>` overrides it with `git rev-parse <ref>`.

```console
$ git rev-parse --abbrev-ref HEAD
```

```console
$ git status --porcelain
```

```console
$ git log --oneline "${BASELINE_SHA}..HEAD"
```

```console
$ git log --merges --oneline "${BASELINE_SHA}..HEAD"
```

With `--since=<ref>` and `--apply-rebase`, confirm the ref precedes
`HEAD`; autosquash on a sibling branch destroys topology:

```console
$ git merge-base --is-ancestor "<ref>" HEAD
```

Halt with a clear message when any of these holds:

- The working tree is dirty (`git status --porcelain` is non-empty; it
  covers dirty submodules).
- The range holds no commits.
- The current branch is the trunk.
- A rebase is in progress. `.git` is a file in a linked worktree, so
  resolve each path with `git rev-parse --git-path rebase-merge` and
  `git rev-parse --git-path rebase-apply`, and test the printed paths.
- `HEAD` is detached.
- The branch has merge commits and `--apply-rebase` was passed.
- `--since=<ref>` with `--apply-rebase` names a ref that is not an
  ancestor of `HEAD`.

## Step 2: Pushed-branch gate

```console
$ git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null
```

No upstream means a local-only branch; continue. With an upstream:

```console
$ git merge-base --is-ancestor "$(git rev-parse '@{u}')" HEAD
```

Exit 0 means the upstream is reachable from `HEAD`: the branch was
pushed. A non-zero exit with an upstream set means a local rewrite
diverged from it; that branch was pushed too. Without `--force-rewrite-pushed`, refuse:

> This branch was already pushed to `<upstream>`. Rewriting its
> history will require a force-push and may break a reviewer's local
> checkout. Re-run with `--force-rewrite-pushed` to override, or use
> `--apply-patches` (no rebase) to apply fixups without rewriting.

With the flag, record the upstream in the final report and continue.

## Step 3: Discover quality gates

Follow `../../references/verification-gates.md` § Local gate buckets;
this skill ignores `build` and the CI-coverage pass. Skip empty buckets
in Steps 11 and 12. With no question tool and no conventions file,
treat the answer as `skip` and warn that no gate will run. When every bucket is `unset` and an apply flag was passed,
warn before Step 10 that no gate will validate the result.

## Step 4: Read project tone

Follow `../../references/detect-pipeline.md` § Tone calibration.

## Step 5: Load the signatures registry

Follow `../../references/detect-pipeline.md` § Registry load. Registry
source: `../../references/signatures.yml`.

## Step 6: Detect

Regex first (cheap, deterministic), semantic verification only on
flagged hunks (expensive, precise).

**Pass A.** Follow `../../references/detect-pipeline.md` § Pass A. Run
each signature's `pattern` against its `target`:

- `diff`: `git diff "${BASELINE_SHA}..HEAD"`, per hunk.
- `message-subject`: each commit's subject line.
- `message-body`: each commit's body.
- `file`: the file content at each commit.

A match yields `{commit_sha, signature_id, location, tier,
confidence: regex, action}`.

**Pass B.** Follow `../../references/detect-pipeline.md` § Pass B with a
commit as the unit. Pass the commit's full diff (`git show <sha>`) and
message.

## Step 7: Apply tiers, budget, and grouping

Apply `../../references/detect-pipeline.md` § Budget and confirmation,
ranking by commits affected.

Group findings by target commit:

| Finding scope | Patch shape | Mechanism |
|---|---|---|
| Diff slop in commit X | One fixup commit per patch | `git commit --fixup=<X>` |
| Subject or body slop in commit X | One reword commit per X | An empty commit whose message is `amend! <subject>` plus the replacement text |
| Whole-commit low-value, or a multi-topic commit | Advisory only | Dropping or splitting is the user's `git rebase -i` |

Autosquash folds fixups that share a target. It reads an `amend!` commit
only from git 2.32 on; check `git --version`, and on older git list each
reword in `advisory.md` as a manual note and keep the diff fixups.

Write replacement messages per `../../references/prose-rules.md`, in
the project's commit-message convention from the conventions files. A
message carries no `Co-Authored-By:` line, no "Generated with" or other
tool trailer, and no emoji; hosts add these by default, so strip them.

## Step 8: Materialize the patch series

Always materialize first; the series is the user's review surface. The
run directory resolves through `git rev-parse --git-path`, so it works
in a linked worktree where `.git` is a file. Create it and print its
path:

```console
$ d=$(git rev-parse --git-path "deslop/$(date -u +%Y%m%d-%H%M%SZ)-$$") && mkdir -p "$d" && echo "$d"
```

Shell state does not persist between Bash calls: use the printed path
literally as `<run-dir>` in every later command, and likewise the
literal values of `BASELINE_SHA`, `START_SHA`, and the gate commands
recorded in `0000-PLAN.md`.

Layout:

```
<run-dir>/
├── 0000-PLAN.md                 (plan + registry source path + SHA-256)
├── NNNN-fixup-<sha>-<id>.patch  (one per diff finding)
├── NNNN-reword-<sha>.txt        (replacement message for <sha>)
├── advisory.md                  (Tier C, over-budget, declined, whole-commit findings)
├── reword/
│   └── <sha>.txt                (one file per target SHA needing reword)
├── reword-map.tsv               (autosquash-subject → target-sha → reword-file)
├── .checkpoint/                 (per-step markers for apply.sh idempotency)
└── apply.sh                     (rendered by ../../scripts/render_apply.py)
```

`0000-PLAN.md` records the registry version, source path, and SHA-256,
the resolved `FORMAT_CMD` / `LINT_CMD` / `TYPECHECK_CMD` / `TEST_CMD`,
`BASELINE_SHA`, the commit range, the budget, and the tone-calibration
result.

Render `apply.sh` with the tested script, passing the literal
`<run-dir>`, `BASELINE_SHA`, and the trunk ref. It
hashes the registry, fills the template, marks the file executable, and
prints its path:

```console
$ python3 ../../scripts/render_apply.py \
    --run-dir "<run-dir>" \
    --baseline "<BASELINE_SHA>" \
    --trunk-ref "origin/<trunk>"
```

The registry defaults to the bundled `signatures.yml`; with
`--taxonomy=<path>`, add `--registry "<path>"`.

`apply.sh` is the one artifact the user runs. It is idempotent through
checkpoints, recomputes the registry SHA-256 recorded in `0000-PLAN.md`,
and aborts if the registry changed. Its exit codes are in the header of
`../../references/apply-template.sh`.

Without an apply flag, print the Step 12 report (skip its git and gate
commands) and stop, telling the user how to run
`bash <run-dir>/apply.sh`. The directory is run-scoped, not
a permanent record.

## Step 9: Confirmation gate

Reached only when `--apply-patches` or `--apply-rebase` was passed. Ask
through `AskUserQuestion`:

| Choice | Effect |
|---|---|
| **Patches only** (default) | Nothing is applied. |
| **Apply patches now** | Run `apply.sh`; fixup commits land on `HEAD`; no rebase. |
| **Apply and autosquash** | Full rewrite. Offered only with `--apply-rebase`, and only when Step 1 found no merge commits. |
| **Cancel** | Delete `<run-dir>/` and exit. |

Without a question tool (Codex, headless), take **Patches only** and
print the `apply.sh` command. A
request that explicitly says to apply patches, or to apply and
autosquash, approves that choice only, never a push.

Before "Apply patches now", show this warning:

> Fixup commits will be on `HEAD`. Run `git rebase -i --autosquash
> <trunk>` yourself before pushing, or reviewers will see the raw
> `fixup!` and `amend!` commits. A backup branch is created for this
> option too.

## Step 10: Backup and apply

Before any history-affecting action, including "Apply patches now",
create the backup branch:

```console
$ git branch "$(git branch --show-current)-pre-deslop-$(date -u +%Y%m%d-%H%M%S)"
```

Record its name in the final report and tell the user that
`git reset --hard <backup>` restores the original state.

```console
$ bash "<run-dir>/apply.sh"
```

`apply.sh` stages explicit paths
only and never uses `git add -A` or `git add .`. Reword commits are
empty by design and are the only empty commits the skill creates.

"Apply patches now" stops here. Steps 11 and 12 follow "Apply and
autosquash" only.

Autosquash runs with `rerere` enabled. Reword commits carry their
replacement message in the body, so no editor is needed:

```console
$ GIT_SEQUENCE_EDITOR=: git \
    -c rerere.enabled=true \
    -c rerere.autoupdate=true \
    rebase -i --autosquash "${BASELINE_SHA}"
```

`GIT_SEQUENCE_EDITOR=:` accepts the generated todo list unattended.
Exit 0 skips to Step 12.

## Step 11: Conflict loop

Follow `../../references/conflict-loop.md` until the rebase completes or
is aborted. On abort, remind the user that the Step 10 backup branch
exists.

## Step 12: Final verification and report

```console
$ git log --oneline "${BASELINE_SHA}..HEAD"
```

```console
$ git status --porcelain
```

Run the full gate set on the tip, skipping empty buckets:

```console
$ ${FORMAT_CMD}
```

```console
$ ${LINT_CMD}
```

```console
$ ${TYPECHECK_CMD}
```

With `--run-tests`:

```console
$ ${TEST_CMD}
```

Report exact counts, not the plan's ranges. The hero line is `Slop
summary`; sections follow in the order shown: summary block,
`Quality gates (final)`, then the `Patch series:` line. A halted or
refused run prints one sentence naming the cause, then what the user
must do (commit or stash, or re-run with `--force-rewrite-pushed`):

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
Slop summary
============
Budget: default
Findings: 4 (2 Tier A, 1 Tier B, 1 Tier C)
Applied: 2 Tier A
Proposed and accepted: 1 Tier B (0 declined)
Advisories: 1 Tier C (see advisory.md)

Tone calibration: demoted "robust"
Verifier: enabled (6 commits scanned; 0 skipped)

Commits: 6 -> 5
  - 1 fixup squashed
Backup branch: feat-login-pre-deslop-20261005

Quality gates (final)
=====================
format=pass | lint=pass | typecheck=pass | tests=skipped

Patch series: <run-dir>
```

`<run-dir>` is the path Step 8 printed. In audit mode, "Applied" is 0 and the Commits and gate lines are omitted.

Do not push; the user decides. After `--force-rewrite-pushed`, recommend
`git push --force-with-lease --force-if-includes` over `git push --force`.

## Edge cases

| Case | Behavior |
|---|---|
| Merge commits in range, no `--apply-rebase` | Permitted; patches and fixups work, and the user can rebase later with `--rebase-merges`. |
| Root commit in range | Warn; rewriting it needs `git rebase --root`. |
| Empty diff after an edit | Skip the fixup and record a no-op. |
| Single-commit branch, no body | A reword commit autosquashes cleanly. |
| `--message-only` and diff slop exists | Report the skipped diff findings; build reword commits only. |
| Linked worktrees | Permitted; run directories resolve through `git rev-parse --git-path`. |
| Existing `fixup!` or `amend!` commits on the branch | Detect with `git log --grep='^fixup!' --grep='^amend!'`; offer to autosquash them first. |
| Non-UTF-8 commit message | Skip message checks for it; warn. |
| Pre-commit hook changes staged content during a fixup | `apply.sh` aborts that step with the hook's stderr; the user fixes it and re-runs. The skill never uses `--no-verify`. |
| `.gitignore` covers a file a patch modifies | `git add` fails; `apply.sh` aborts that step. |
| Git older than 2.32 | See Step 7. |
| Override file is git-tracked and dirty | Warned at Step 5 (see Registry load). |
| Registry edited between materialize and apply | `apply.sh` exits 1. |
