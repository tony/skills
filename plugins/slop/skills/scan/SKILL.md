---
name: scan
description: "Use when scanning tracked repository files for AI slop, verbosity, brittle references, or low-value contributions."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
argument-hint: "[--paths=<glob>] [--apply] [--budget=strict|default|lax] [--with-history=<N>] [--allow-dirty] [--run-tests] [--no-semantic] [--taxonomy=<path>] [--on-fail=skip|stop|ask]"
user-invocable: true
disable-model-invocation: true
---

# `/slop:scan`

Repo-wide slop scanner. Audits every tracked file at HEAD for AI slop,
verbose code and comments, fragile hard-coded references, and low-value
contributions. Optionally scans recent history, advisory only. With
`--apply`, each finding becomes its own forward-going commit after the
project's quality gates pass.

The skill never rewrites history. It only adds commits at `HEAD`, so it
is safe on pushed branches and cannot flatten merge topology. For
branch-scoped cleanup with fixups and autosquash, use `/slop:deslop`.
The PR description is out of scope.

Invoked by name only: it edits files and creates commits, so it must be
user-explicit, never router-inferred.

Slop is a workflow label, not proof the text is wrong; reduce
review-hostile noise and leave the author's voice alone. Flag
branch-internal narrative (renames of unshipped symbols, intermediate
states, `### Fixes` for bugs no release had) only when no user of the
latest published release experienced the old name, behavior, or bug.

## `$ARGUMENTS` contract

An empty `$ARGUMENTS` scans all tracked files at HEAD with the default
budget. A non-flag token is a path scope that overrides `--paths`.

| Flag | Default | Effect |
|---|---|---|
| `--paths=<glob>` | all tracked | Scope through `git ls-files`; comma-separate multiple globs. |
| `--apply` | off | Offer the per-finding commit loop at the Step 9 gate. **Lands new commits on `HEAD`.** Without it the run stops after writing the patch series. |
| `--budget=<level>` | `default` | Tier ceiling; table in `../../references/detect-pipeline.md` § Budget and confirmation. |
| `--with-history=<N>` | off | Also scan the last N commits' content and messages. Findings are advisory only. N is capped at the commit count, with a warning. |
| `--allow-dirty` | off | Permit a dirty working tree. Files already dirty at Step 1 are advisory only; the skill never edits or rolls back a file with pre-existing changes. Without the flag, a dirty tree halts at Step 1. |
| `--run-tests` | off | Include the test command in per-commit gates and final verification. |
| `--no-semantic` | off | Skip the Pass B verifier; regex only. |
| `--taxonomy=<path>` | built-in + `.claude/slop.local.yml` | Replace the registry; the built-in set and the override are both ignored. |
| `--on-fail=<mode>` | `skip` | On a per-finding gate failure: `skip` (roll back, mark `gate-failed`, continue), `stop` (roll back, halt), `ask` (surface through `AskUserQuestion`). |

## Orchestration Plan

Follow `../../references/detect-pipeline.md` § Orchestration plan. The
plan contains:

1. `BASELINE_SHA` and the working-tree state (clean, or dirty with
   `--allow-dirty` and the list of dirty files).
2. The scope: globs and total file count.
3. Whether `--with-history=N` is active, and the resolved N.
4. Quality-gate commands per bucket: `set`, `unset`, or `prompt-user`.
5. The active `--budget` and `--on-fail`.
6. The mode: `audit` or `apply-and-commit`.
7. A findings summary as ranges.

## Step 1: Snapshot state and lock the baseline

Resolve `BASELINE_SHA` per `../../references/detect-pipeline.md` §
Baseline; it comes from the last fetch and may be stale, which only
affects tone calibration. Then record the starting commit:

```console
$ git rev-parse HEAD
```

Store it as `START_SHA`; the final report lists commits after it.

```console
$ git rev-parse --abbrev-ref HEAD
```

```console
$ git status --porcelain
```

With `--allow-dirty`, keep the paths from `git status --porcelain` as
`DIRTY_AT_START`.

Halt with a clear message when any of these holds:

- The working tree is dirty and `--allow-dirty` was not passed.
- A rebase or merge is in progress (`.git/rebase-merge/`,
  `.git/rebase-apply/`, or `.git/MERGE_HEAD` exists).
- `HEAD` is detached; every commit needs a branch reference.

## Step 2: Resolve scan scope

```console
$ git ls-files
```

With `--paths=<glob>`, pass each glob through:

```console
$ git ls-files -- "<glob>"
```

Refuse an empty set with "scope is empty"; a misspelled glob must not
silently no-op.

With `--with-history=N`, first cap N at the commit count:

```console
$ git rev-list --count HEAD
```

Then collect the history, from `HEAD` so it also works on the trunk:

```console
$ git log -n "${N}" -p HEAD
```

Feed it to Pass A with a `historical_only=true` marker.

## Step 3: Discover quality gates

Follow `../../references/verification-gates.md` § Local gate buckets;
this skill ignores `build` and the CI-coverage pass. With no question
tool and no conventions file, treat the answer as `skip` and warn that
no gate will run. Skip empty buckets in the
apply loop and final verification. When every bucket is `unset` and
`--apply` was passed, warn before continuing that commits will land
without gate validation.

## Step 4: Read project tone

Follow `../../references/detect-pipeline.md` § Tone calibration.

## Step 5: Load the signatures registry

Follow `../../references/detect-pipeline.md` § Registry load. Registry
source: `../../references/signatures.yml`.

## Step 6: Detect

Regex first (cheap, deterministic), semantic verification only on
flagged files (expensive, precise).

**Pass A.** Follow `../../references/detect-pipeline.md` § Pass A. Run
each signature's `pattern` against its `target`:

- `file`: every file from Step 2, per line.
- `diff`: the same files, read as current content. This skill matches
  file state, not patches, so strip a leading `^\+` from the pattern and
  treat every line as added. Skip patterns that begin with `^-`: they
  cannot match file content, and stay active under `--with-history`
  against the `git log -p` output.
- `message-subject` and `message-body`: only under `--with-history`,
  against the captured log.

A match yields `{file, line_range, signature_id, tier,
confidence: regex, action, historical_only: <bool>}`. A finding with
`historical_only: true` is advisory at any tier, because the skill
cannot edit historical commits. A finding in a file listed in
`DIRTY_AT_START` is advisory too.

**Pass B.** Follow `../../references/detect-pipeline.md` § Pass B with a
file as the unit. Pass the file's full content.

## Step 7: Apply tiers, budget, and grouping

Apply `../../references/detect-pipeline.md` § Budget and confirmation,
ranking by files affected.

Group findings by file and shape each patch:

| Finding scope | Patch shape |
|---|---|
| One regex match in a file | One `.patch` file, one commit. |
| Several matches of one signature in a file | Each match is its own finding and its own commit. |
| Semantic-only finding | One `.patch` file, one commit. |
| Whole-file low-value (for example, debug debris) | Advisory; never applied, because deletion is too consequential. |
| Historical-only finding | Advisory; never an editable patch. |

One finding per commit keeps each change individually reviewable and
revertable with `git revert <sha>`, at the cost of N commits for N
findings. For aggregation, use `/slop:deslop`.

## Step 8: Materialize the patch series

Always materialize first; the series is the user's review surface. The
run directory resolves through `git rev-parse --git-path`, so it works
in a linked worktree where `.git` is a file. Create it and print its
path:

```console
$ d=$(git rev-parse --git-path "slop-scan/$(date -u +%Y%m%d-%H%M%SZ)-$$") && mkdir -p "$d" && echo "$d"
```

Shell state does not persist between Bash calls: use the printed path
literally as `<run-dir>` in every later command, and likewise the
literal values of `BASELINE_SHA`, `START_SHA`, and the gate commands
recorded in `0000-PLAN.md`.

Layout:

```
<run-dir>/
├── 0000-PLAN.md                       (plan + registry source path + SHA-256)
├── NNNN-edit-<file-slug>-<sigid>.patch
├── advisory.md                        (Tier C, over-budget, declined, historical-only, dirty-file findings)
└── commits.json                       (finding → proposed commit subject + body)
```

`0000-PLAN.md` records the registry version, source path, and SHA-256,
the resolved `FORMAT_CMD` / `LINT_CMD` / `TYPECHECK_CMD` / `TEST_CMD`,
`BASELINE_SHA`, the scope's file count, the budget, the tone-calibration
result, the `--on-fail` mode, and `DIRTY_AT_START`.

`commits.json` holds, per finding, the proposed subject and the `why:` /
`what:` body, built from `../../references/commit-template.md` and
written per `../../references/prose-rules.md`. The user may edit it
before the apply loop reads it. The skill drives the loop itself; there
is no `apply.sh`.

Without `--apply`, print the Step 11 report (skip its git and gate
commands; counts of committed and rolled-back findings are 0) and stop.
The user re-invokes with `--apply` once the proposals look right. The directory is run-scoped, not a permanent
record.

## Step 9: Confirmation gate

Reached only with `--apply`. Ask through `AskUserQuestion`:

| Choice | Effect |
|---|---|
| **Patches only** (default) | Nothing is applied. |
| **Apply and commit** | Run the per-finding commit loop. |
| **Cancel** | Delete `<run-dir>/` and exit. |

Without a question tool (Codex, headless), take **Patches only**. A
request that explicitly says to apply and commit approves that choice
only, never a push.

## Step 10: Per-finding commit loop

Take findings in order of `(file ASC, signature_id ASC,
line_range_start ASC)`.

### 10a. Apply the edit

Use the Edit tool. The `old_string` and `new_string` come from the
regex match (Pass A) or the sub-agent's suggestion (Pass B), as recorded
in the finding's `.patch` file.

### 10b. Stage explicit paths

```console
$ git add -- "<file>"
```

Never `git add -A` or `git add .`.

### 10c. Run touched-file gates

Scope each gate to the touched file where the tool takes a path
argument; otherwise run project-wide. With `--allow-dirty`, run only
gates that take a path, skip the others, and report them as skipped, so
a project-wide formatter cannot rewrite the user's dirty files.

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

- The formatter applies its changes; re-stage only `<file>` with
  `git add -- "<file>"`. A project-wide formatter may also rewrite other
  files: after the gates, run `git status --porcelain`, and restore
  every path other than `<file>` with
  `git restore --source=HEAD --staged --worktree -- "<path>"` so the
  next finding starts from a clean tree. A path in `DIRTY_AT_START` is
  never restored; treat a change to it as a gate failure.
- A linter with `--fix` applies fixes; re-stage. An error it cannot fix
  is a gate failure.
- A type checker never modifies files; its errors are gate failures.
- Test failures are gate failures.

### 10d. On gate failure

Roll the file back with a command that drops both the index and worktree
change. The file is never one of `DIRTY_AT_START`, so no user edit is
lost:

```console
$ git restore --source=HEAD --staged --worktree -- "<file>"
```

Then apply `--on-fail`:

- `skip` (default): record the gate's stderr, mark the finding
  `gate-failed`, continue.
- `stop`: record stderr and halt.
- `ask`: ask through `AskUserQuestion`: **Edit and continue** (the user
  fixes the file; re-run the gates), **Skip this finding** (roll back
  and continue), or **Stop the run** (roll back and halt). Without a
  question tool, behave as `skip`.

### 10e. On gate pass

Read the finding's message from `commits.json` and write it to a temp
file made with `mktemp "${TMPDIR:-/tmp}/slop-msg.XXXXXX"`. Commit with
it, then delete the file:

```console
$ git commit -F "<temp-message-file>"
```

The message carries no `Co-Authored-By:` line, no "Generated with" or
other tool trailer, and no emoji; hosts add these by default, so strip
them before committing.

If a `pre-commit` or `commit-msg` hook rejects the commit, treat it as a
gate failure: roll back as in 10d, mark the finding `hook-failed`,
surface the hook's stderr, and apply `--on-fail`. Never use
`--no-verify`; hooks are the project's authority.

Mark the finding `committed`.

## Step 11: Final verification and report

```console
$ git log --oneline "${START_SHA}..HEAD"
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

The hero line is `Slop scan summary`; sections follow in the order
shown: summary block, `Quality gates (final)`, `Per-finding commits`,
`Gate-failed findings`, then the `Patch series:` line. A halted run
prints one sentence naming the cause, then what the user must do (commit
or stash, or pass `--allow-dirty`).

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
Slop scan summary
=================
Scope: 42 files (paths: src/**, docs/**)
Budget: default
Findings: 5 (2 Tier A, 2 Tier B, 1 Tier C, 0 historical-only)

Committed: 3 findings landed as commits
Gate-failed (rolled back): 1 (details below)
Hook-failed (rolled back): 0
Advisory: 1 (see advisory.md)
Historical-only: 0

Tone calibration: demoted "robust", "seamless"
Verifier: enabled (42 files scanned; 0 skipped)

Quality gates (final)
=====================
format=pass | lint=pass | typecheck=pass | tests=skipped

Per-finding commits:
  7c1e9d4 chore(slop[low-value.todo-noise]) Remove vague TODO from src/utils.py
  a02b5f1 docs(slop[brittle.line-numbers]) Replace line number in CONTRIBUTING.md

Gate-failed findings:
  brittle.test-count in docs/guide.md:12, lint: line too long

Patch series: .git/slop/run-1/
```

Do not push; the user decides. A plain `git push` suffices because no
history changed.

## Edge cases

| Case | Behavior |
|---|---|
| Empty repo or no tracked files | Exit cleanly: "No tracked files to scan." |
| All findings advisory (Tier C only at `default` budget) | Print the report; no commits; exit 0. |
| `--allow-dirty` and a finding sits in a dirty file | Advisory only; never edited. |
| Finding's edit yields an empty diff (already fixed) | Skip; record "no-op"; never create an empty commit. |
| Two findings target the same line range | Apply in `(signature_id ASC, line_range_start ASC)` order; the second usually becomes a no-op. |
| Disk fills while writing a patch | Treat as a gate failure for that finding and follow `--on-fail`. |
| Binary file | Pass A skips it; it yields no findings. |
| Symlink | Skip it; the link target is out of scope. |
