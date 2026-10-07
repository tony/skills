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

With `--apply-rebase`, the skill refuses a pushed branch without
`--force-rewrite-pushed`, and refuses a branch holding merge commits, because
`git rebase -i --autosquash` without `--rebase-merges` flattens topology.

Slop is a workflow label, not proof the text is wrong; reduce
review-hostile noise and leave the author's voice alone. Flag
branch-internal narrative (renames of unshipped symbols, intermediate
states, `### Fixes` for bugs no release had) only when no user of the
latest published release experienced the old name, behavior, or bug.

`<slop_detect.py>` is `../../scripts/slop_detect.py` and `<render_apply.py>`
is `../../scripts/render_apply.py`, resolved from this skill's directory,
not the repository root. Resolve each to an absolute path once, print it,
and write that literal path in every command below, since shell variables
do not persist between Bash calls. Both need python3 (3.9 or newer).

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
| `--force-rewrite-pushed` | off | Let `--apply-rebase` rewrite a branch that was already pushed. |
| `--run-tests` | off | Include the test command in conflict-loop gates and final verification. |
| `--no-semantic` | off | Skip the Pass B verifier; regex only. |
| `--taxonomy=<path>` | built-in + `.claude/slop.local.yml` | Replace the registry; the built-in set and the override are both ignored. |

## Orchestration Plan

Follow `../../references/detect-pipeline.md` § Orchestration plan: run
Step 1 first, then present the plan. The plan contains:

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

Only `--apply-rebase` rewrites history, so only it is gated. Audit and
`--apply-patches` runs skip this step.

```console
$ git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null
```

No upstream means a local-only branch; continue. With an upstream,
count the commits it holds past the baseline:

```console
$ git rev-list --count "${BASELINE_SHA}..@{u}"
```

A count above 0 means the branch was pushed, whether or not `HEAD` still
contains those commits. A count of 0 means the upstream is trunk itself
(a branch cut with `git switch -c x origin/main` tracks it) or sits at
the baseline; nothing of the branch was published, so continue. Without
`--force-rewrite-pushed`, refuse a pushed branch:

> This branch was already pushed to `<upstream>`. Rewriting its
> history requires a force-push, and reviewers must reset their local
> checkouts. Re-run with `--force-rewrite-pushed` to override, or drop
> `--apply-rebase` and use `--apply-patches` to add fixup commits
> without rewriting.

With the flag, record the upstream in the final report and continue.

## Step 3: Discover quality gates

Follow `../../references/verification-gates.md` § Local gate buckets,
then `../../references/detect-pipeline.md` § Gate handling. Skip empty
buckets in Steps 11 and 12; the no-gate warning comes before Step 10.

## Step 4: Read project tone

Follow `../../references/detect-pipeline.md` § Tone calibration.

## Step 5: Load the signatures registry

Follow `../../references/detect-pipeline.md` § Registry load. Registry
source: `../../references/signatures.yml`.

## Step 6: Detect

Regex first (cheap, deterministic), semantic verification only on
flagged hunks (expensive, precise).

**Pass A.** Follow `../../references/detect-pipeline.md` § Pass A. Pass
`--override .claude/slop.local.yml` when that file exists; with
`--taxonomy=<path>`, pass it as `--registry` and drop `--override`.

- `diff` (skip under `--targets=messages`): one commit at a time, oldest
  first, so each finding names the commit that added the line.

```console
$ git log -p --reverse "<BASELINE_SHA>..HEAD" | python3 <slop_detect.py> diff \
    --registry ../../references/signatures.yml
```

- `message-subject` and `message-body` (skip under `--targets=diff`):

```console
$ git log -z --format=%H%x1f%B "<BASELINE_SHA>..HEAD" | python3 <slop_detect.py> messages \
    --registry ../../references/signatures.yml
```

Drop a diff finding whose `text` no longer appears in its file at `HEAD`
(`git grep -F -e "<text>" HEAD -- "<file>"`): a later commit removed
it, and its fixup could not apply. Then run the Guard check. A finding
has `{commit_sha, signature_id, file, line_start, tier, confidence: regex,
action}`.

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

Number the diff patches by `(target commit, oldest first; file;
line_start)`. `apply.sh` applies them in number order and `git apply`
exits 3 on a stale hunk, so cut each patch against the tree the earlier
patches leave, never against `HEAD` alone. Step 8 does this in a scratch
worktree.

Autosquash folds fixups that share a target. It reads an `amend!` commit
only from git 2.32 on; check `git --version`, and on older git list each
reword in `advisory.md` as a manual note and keep the diff fixups.

Write replacement messages per `../../references/prose-rules.md`, in
the project's commit-message convention from the conventions files. A
message carries no `Co-Authored-By:` line, no "Generated with" or other
tool trailer, and no emoji; hosts add these by default, so strip them.

## Step 8: Materialize the patch series

Always materialize first; the series is the user's review surface.
Create the run directory per `../../references/detect-pipeline.md` §
Run directory, with `<name>` = `deslop`.

Cut the diff patches sequentially. Before creating the scratch worktree,
compare two physical paths: print the repository root, then the physical
home path.

```console
$ git rev-parse --show-toplevel
```

```console
$ cd ~ && pwd -P
```

Refuse when the two are equal or the root is an ancestor of home: a
dotfile repo rooted at home would check out the whole home directory. A
string compare against `$HOME` misses a symlinked home. Make the
scratch directory and print it:

```console
$ mktemp -d "${TMPDIR:-/tmp}/deslop-scratch.XXXXXX"
```

Use the printed path literally as `<scratch>`:

```console
$ git worktree add --detach "<scratch>" HEAD
```

For each finding in number order, make its edit inside `<scratch>`,
write that file's diff as the finding's patch, then stage the file so the
next diff starts from the edited state:

```console
$ git -C "<scratch>" diff -- "<file>"
```

```console
$ git -C "<scratch>" add -- "<file>"
```

When every patch is cut, remove the worktree:

```console
$ git worktree remove --force "<scratch>"
```

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

`0000-PLAN.md` adds the commit range to the fields in § Run directory.

Render `apply.sh` with the tested script, passing the literal
`<run-dir>`, `BASELINE_SHA`, and the trunk ref. It
hashes the registry, fills the template, marks the file executable, and
prints its path:

```console
$ python3 <render_apply.py> \
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
`bash <run-dir>/apply.sh`.

## Step 9: Confirmation gate

Reached only when `--apply-patches` or `--apply-rebase` was passed.
Follow `../../references/detect-pipeline.md` § Confirmation gate with
these choices:

| Choice | Effect |
|---|---|
| **Patches only** (default) | Nothing is applied. |
| **Apply patches now** | Run `apply.sh`; fixup commits land on `HEAD`; no rebase. |
| **Apply and autosquash** | Full rewrite. Offered only with `--apply-rebase`, and only when Step 1 found no merge commits. |
| **Cancel** | Delete `<run-dir>/` and exit. |

Headless, the printed command is `bash <run-dir>/apply.sh`. "Apply the
patches" approves **Apply patches now** and nothing broader: not
autosquash, not a push. "Apply and autosquash" approves that choice.

Before "Apply patches now", show this warning:

> Fixup commits will be on `HEAD`. Run `git rebase -i --autosquash
> <trunk>` yourself before pushing, or reviewers will see the raw
> `fixup!` and `amend!` commits. A backup branch is created for this
> option too.

## Step 10: Backup and apply

Run the series. Before its first commit, `apply.sh` creates a backup
branch at the starting tip and prints `Backup branch: <name>`; a re-run
prints the same name:

```console
$ bash "<run-dir>/apply.sh"
```

Record that name in the final report and tell the user that
`git reset --hard <backup>` restores the original state.

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

Run `git status --porcelain` once more. A formatter that rewrote files
leaves a dirty tree: add `Gate left uncommitted changes: <paths>` under
`Quality gates (final)`, and never commit or restore them.

Report exact counts, not the plan's ranges. The hero line is `Slop
summary`; sections follow in the order shown: summary block,
`Quality gates (final)`, then the `Patch series:` line when nothing was
applied. A halted or
refused run prints one sentence naming the cause, then what the user
must do (commit or stash, or re-run with `--force-rewrite-pushed`):

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Slop summary
============
Budget: default
Findings: 4 (2 Tier A, 1 Tier B, 1 Tier C)
Applied: 3 (2 Tier A, 1 Tier B; 0 declined)
Advisories: 1 Tier C (see advisory.md)

Tone calibration: demoted "robust"
Verifier: enabled (6 commits scanned; 0 skipped)

Commits: 6 (3 fixups folded)
Backup branch: feat-login-pre-deslop-20261005-142530

Quality gates (final)
=====================
format=pass | lint=pass | typecheck=pass | tests=skipped
```

An audit run ends with `Patch series: <run-dir>`, the path Step 8
printed, and omits the Commits, Backup branch, and gate lines; "Applied"
is 0.

Do not push; the user decides. After `--force-rewrite-pushed`, recommend
`git push --force-with-lease --force-if-includes` over `git push --force`.

End with the next step, through `AskUserQuestion` when available,
otherwise as a plain line: after an audit, `bash <run-dir>/apply.sh` or
a re-run with `--apply-patches`; after an apply, the push command.

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
