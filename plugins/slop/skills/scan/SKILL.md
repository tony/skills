---
name: scan
description: "Use when scanning tracked repository files for AI slop, verbosity, brittle references, or low-value contributions."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
argument-hint: "[--paths=<glob>] [--apply] [--from=<run-dir>] [--budget=strict|default|lax] [--with-history=<N>] [--allow-dirty] [--run-tests] [--no-semantic] [--taxonomy=<path>] [--on-fail=skip|stop|ask]"
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
| `--from=<run-dir>` | off | With `--apply`, reuse a series an earlier run materialized instead of detecting again, so edits to its `commits.json` are honored. Halts when `HEAD` moved since. |
| `--budget=<level>` | `default` | Tier ceiling; table in `../../references/detect-pipeline.md` § Budget and confirmation. |
| `--with-history=<N>` | off | Also scan the last N commits' content and messages. Findings are advisory only. N is capped at the commit count, with a warning. |
| `--allow-dirty` | off | Permit a dirty working tree. Files already dirty at Step 1 are advisory only; the skill never edits or rolls back a file with pre-existing changes. Without the flag, a dirty tree halts at Step 1. |
| `--run-tests` | off | Include the test command in per-commit gates and final verification. |
| `--no-semantic` | off | Skip the Pass B verifier; regex only. |
| `--taxonomy=<path>` | built-in + `.claude/slop.local.yml` | Replace the registry; the built-in set and the override are both ignored. |
| `--on-fail=<mode>` | `skip` | On a per-finding gate failure: `skip` (roll back, mark `gate-failed`, continue), `stop` (roll back, halt), `ask` (surface through `AskUserQuestion`). |

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in
Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Follow `../../references/detect-pipeline.md` § Orchestration plan: run
Step 1 first, then present the plan. The plan contains:

1. `BASELINE_SHA` and the working-tree state (clean, or dirty with
   `--allow-dirty` and the list of dirty files).
2. The scope: globs and total file count.
3. Whether `--with-history=N` is active, and the resolved N.
4. Quality-gate commands per bucket: `set`, `unset`, or `prompt-user`.
5. The active `--budget` and `--on-fail`.
6. The mode: `audit` or `apply-and-commit`.
7. A findings summary as ranges.

## Step 1: Snapshot state and lock the baseline

Check for an unborn branch first: staged files pass `git ls-files` but
leave no `HEAD` to scan.

```console
$ git rev-parse --verify --quiet HEAD
```

A non-zero exit means no commits. Stop with one result sentence, then
what the user must do. Do not list what was not done:

```text
No commits yet. Commit the files you want checked, then run /slop:scan again.
```

Then check for tracked files:

```console
$ git ls-files | head -n 1
```

If it prints nothing, stop the same way:

```text
No tracked files to scan. Commit the files you want checked, then run /slop:scan again.
```

Resolve `BASELINE_SHA` per `../../references/detect-pipeline.md` §
Baseline; it comes from the last fetch and may be stale, which only
affects tone calibration. Without a trunk it skips calibration. Then
record the starting commit:

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
- A rebase or merge is in progress. `.git` is a file in a linked
  worktree, so resolve each of `rebase-merge`, `rebase-apply`, and
  `MERGE_HEAD` with `git rev-parse --git-path <name>` and test the
  printed paths.
- `HEAD` is detached; every commit needs a branch reference.
- `--from` was passed without `--apply`, or `<run-dir>/0000-PLAN.md` is
  missing, or its recorded `START_SHA` differs from `HEAD`, or the
  registry SHA-256 it records changed. Say that the series is stale and
  to re-run `--apply` without `--from`.

With `--from=<run-dir>`, read the scope, gate commands, `--on-fail`, and
`DIRTY_AT_START` from `0000-PLAN.md`, skip Steps 2 to 8, and go to Step 9.

## Step 2: Resolve scan scope

Only counts are needed here; Step 6 streams the content to the matcher.

```console
$ git ls-files | wc -l
```

With `--paths=<glob>`, count each glob instead:

```console
$ git ls-files -- "<glob>" | wc -l
```

Refuse an empty set with "scope is empty"; a misspelled glob must not
silently no-op.

With `--with-history=N`, cap N at the commit count, with a warning:

```console
$ git rev-list --count HEAD
```

Step 6 reads that history from `HEAD`, so it also works on the trunk.

## Step 3: Discover quality gates

Follow `../../references/verification-gates.md` § Local gate buckets,
then `../../references/detect-pipeline.md` § Gate handling. The no-gate
warning says commits will land without gate validation.

## Step 4: Read project tone

Follow `../../references/detect-pipeline.md` § Tone calibration.

## Step 5: Load the signatures registry

Follow `../../references/detect-pipeline.md` § Registry load. Registry
source: `../../references/signatures.yml`.

## Step 6: Detect

Regex first (cheap, deterministic), semantic verification only on
flagged files (expensive, precise).

**Pass A.** Follow `../../references/detect-pipeline.md` § Pass A.
`<slop_detect.py>` is `../../scripts/slop_detect.py`, resolved from this
skill's directory, not the repository root. Resolve it to an absolute
path once, print it, and write that literal path in each command, since
shell variables do not persist between Bash calls. It needs python3 (3.9
or newer).

`<signatures.yml>` is `../../references/signatures.yml`, resolved and
written the same way. Write the literal value of `BASELINE_SHA`,
`START_SHA`, `N`, and each gate command wherever a step shows `<BASELINE_SHA>`
or `<FORMAT_CMD>`.

Run the matcher over the Step 2 files. `files` mode reads each `file`
and `diff` signature against current content; `--added-base` marks the
lines `BASELINE_SHA..HEAD` added, so an added-line rule (`^\+`) stays
Tier A on those lines and drops to Tier B on every other line. Omit
`--added-base` when there is no trunk (every added-line rule then drops
to Tier B), and `--override` when
`.claude/slop.local.yml` is absent; with `--taxonomy=<path>`, pass it as
`--registry` and drop `--override`. With `--paths`, narrow the
`git ls-files -z` list the same way as Step 2.

```console
$ git ls-files -z | python3 <slop_detect.py> files \
    --registry <signatures.yml> \
    --override .claude/slop.local.yml \
    --added-base "<BASELINE_SHA>" \
    --out <findings.json>
```

`--out` writes the JSON to a `mktemp` file (use its literal path later)
and prints counts per tier and signature. Read it with `jq`, not `cat`.

Under `--with-history`, also run the diff and message modes over the
captured log. Their findings carry `historical_only`.

```console
$ git -c core.quotepath=off log -n "<N>" -p HEAD | python3 <slop_detect.py> diff \
    --registry <signatures.yml> \
    --historical
```

```console
$ git log -n "<N>" -z --format=%H%x1f%B HEAD | python3 <slop_detect.py> messages \
    --registry <signatures.yml> \
    --historical
```

Then run the Guard check from the pipeline reference. A finding has
`{file, line_start, signature_id, tier, confidence: regex, action,
historical_only}`. A finding with `historical_only: true` is advisory at
any tier, because the skill cannot edit historical commits. A finding in
a file listed in `DIRTY_AT_START` is advisory too.

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

Always materialize first; the series is the user's review surface.
Create the run directory per `../../references/detect-pipeline.md` §
Run directory, with `<name>` = `slop-scan`.

Layout:

```
<run-dir>/
├── 0000-PLAN.md                       (plan + registry source path + SHA-256)
├── NNNN-edit-<file-slug>-<sigid>.patch
├── advisory.md                        (Tier C, over-budget, declined, historical-only, dirty-file findings)
└── commits.json                       (finding → proposed commit subject + body)
```

`0000-PLAN.md` adds `START_SHA`, the scope's file count, the `--on-fail`
mode, and `DIRTY_AT_START` to the fields in § Run directory.

`commits.json` is a list in apply order. Each entry holds `patch`, `file`,
`signature_id`, and the proposed `subject` and `why:` / `what:` `body`,
built from `../../references/commit-template.md` and written per
`../../references/prose-rules.md`. The user may edit an entry or delete
one to skip it, then re-invoke with `--apply --from=<run-dir>`; the loop
reads the file as it stands. A re-invocation without `--from` detects
again, writes a new run directory, and ignores those edits. The skill
drives the loop itself; there is no `apply.sh`.

Without `--apply`, print the Step 11 report (skip its git and gate
commands; counts of committed and rolled-back findings are 0) and stop.
The user re-invokes with `--apply --from=<run-dir>` once the proposals
look right.

## Step 9: Confirmation gate

Reached only with `--apply`. Follow
`../../references/detect-pipeline.md` § Confirmation gate with these
choices:

| Choice | Effect |
|---|---|
| **Patches only** (default) | Nothing is applied. |
| **Apply and commit** | Run the per-finding commit loop. |
| **Cancel** | Delete `<run-dir>/` and exit. |

Headless, the printed command is the `--apply --from=<run-dir>` re-run. "Apply and
commit" approves **Apply and commit** and nothing broader: no push.

## Step 10: Per-finding commit loop

Take the entries of `commits.json` in order; Step 8 sorted them by
`(file ASC, signature_id ASC, line_range_start ASC)`.

### 10a. Apply the edit

Use the Edit tool. The `old_string` and `new_string` come from the
regex match (Pass A) or the sub-agent's suggestion (Pass B), as recorded
in the finding's `.patch` file.

### 10b. Stage explicit paths

```console
$ git add -- '<file>'
```

Write file names single-quoted, each `'` as `'\''`. Never `git add -A` or `git add .`.

### 10c. Run touched-file gates

Scope each gate to the touched file where the tool takes a path
argument; otherwise run project-wide. With `--allow-dirty`, run only
gates that take a path, skip the others, and report them as skipped, so
a project-wide formatter cannot rewrite the user's dirty files.

```console
$ <FORMAT_CMD>
```

```console
$ <LINT_CMD>
```

```console
$ <TYPECHECK_CMD>
```

With `--run-tests`:

```console
$ <TEST_CMD>
```

- The formatter applies its changes; re-stage only `<file>` with
  `git add -- '<file>'`. A project-wide formatter may also rewrite other
  files: after the gates, run `git status --porcelain` and restore every
  path other than `<file>` with
  `git restore --source=HEAD --staged --worktree -- '<path>'` (for an
  untracked `??` path, `git clean -fd -- '<path>'`), so the next finding
  starts clean. Never restore a `DIRTY_AT_START` path; a change to one
  is a gate failure.
- A linter with `--fix` applies fixes; re-stage. An error it cannot fix
  is a gate failure.
- A type checker never modifies files; its errors are gate failures.
- Test failures are gate failures.

### 10d. On gate failure

Roll the file back with a command that drops both the index and worktree
change. The file is never one of `DIRTY_AT_START`, so no user edit is
lost:

```console
$ git restore --source=HEAD --staged --worktree -- '<file>'
```

Then clean up after a project-wide formatter as in 10c: run
`git status --porcelain` and restore or clean every other path the
gates changed, as above.

Then apply `--on-fail`:

- `skip` (default): record the gate's stderr, mark the finding
  `gate-failed`, continue.
- `stop`: record stderr and halt.
- `ask`: ask through `AskUserQuestion`: **Edit and continue** (the user
  fixes the file; re-run the gates), **Skip this finding** (roll back
  and continue), or **Stop the run** (roll back and halt). Without a
  question tool, behave as `skip`.

### 10e. On gate pass

Read the finding's `subject` and `body` from its `commits.json` entry. Make a temp file with
`mktemp "${TMPDIR:-/tmp}/slop-msg.XXXXXX"` and print its path. Write the
message to it with the Write tool, never a shell heredoc: the text comes
from repo content, and a line equal to the delimiter would end the
heredoc and run the rest as shell. Reuse the printed path literally.
Commit with it, then delete it with `rm -f`:

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
$ git log --oneline "<START_SHA>..HEAD"
```

```console
$ git status --porcelain
```

Run the full gate set on the tip, skipping empty buckets:

```console
$ <FORMAT_CMD>
```

```console
$ <LINT_CMD>
```

```console
$ <TYPECHECK_CMD>
```

With `--run-tests`:

```console
$ <TEST_CMD>
```

Run `git status --porcelain` again. List files a formatter rewrote as
`Gate left uncommitted changes: <paths>` under `Quality gates (final)`;
never commit or restore them.

The hero line is `Slop scan summary`; sections follow in the order
shown: summary block, `Open findings`, `Quality gates (final)`,
`Per-finding commits`, `Gate-failed findings`, then the `Patch series:`
line. `Open findings` lists each Tier A and B finding neither committed nor gate-failed as
`signature_id file:line` (`signature_id <short-sha> subject` or `body`
for a history finding), at most 10, then `and N more`; omit it when none
remain. A halted run
prints one sentence naming the cause, then what the user must do (commit
or stash, or pass `--allow-dirty`).

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Slop scan summary
=================
Scope: 42 files (paths: src/**, docs/**)
Budget: default
Findings: 5 (2 Tier A, 2 Tier B, 1 Tier C, 0 historical-only)

Committed: 3
Gate-failed (rolled back): 1
Hook-failed (rolled back): 0
Advisory: 1 (in advisory.md under the patch series)
Historical-only: 0

Tone calibration: demoted "robust", "seamless"
Verifier: enabled (42 files scanned; 0 skipped)

Quality gates (final)
=====================
format=pass | lint=pass | typecheck=pass | tests=skipped

Per-finding commits
===================
- 7c1e9d4 chore(cleanup) Remove vague TODO from src/utils.py
- a02b5f1 docs(cleanup) Replace line number in CONTRIBUTING.md
- e4410bc docs(cleanup) Drop attribution footer from README.md

Gate-failed findings
====================
- brittle.line-numbers in docs/guide.md:12, lint: line too long

Patch series: <run-dir>
Next: git push
```

`Patch series:` carries the path Step 8 printed; the user reviews
`commits.json` and `advisory.md` there. Do not push; no history
changed, so a plain `git push` suffices.

End with the next step, through `AskUserQuestion` when available,
otherwise as a plain line: after an audit, the `--apply --from=<run-dir>` re-run; after
commits, `git push`.

## Edge cases

| Case | Behavior |
|---|---|
| Empty repo or no tracked files | Step 1 stops with the one-sentence shape. |
| All findings advisory (Tier C only at `default` budget) | Print the report; no commits; exit 0. |
| `--allow-dirty` and a finding sits in a dirty file | Advisory only; never edited. |
| Finding's edit yields an empty diff (already fixed) | Skip; record "no-op"; never create an empty commit. |
| Two findings target the same line range | Apply in `(signature_id ASC, line_range_start ASC)` order; the second usually becomes a no-op. |
| Disk fills while writing a patch | Treat as a gate failure for that finding and follow `--on-fail`. |
| Binary file | Pass A skips it; it yields no findings. |
| Symlink | Skip it; the link target is out of scope. |
