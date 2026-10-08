---
name: slop-scan
description: >-
  Use when scanning tracked repository files for AI slop, verbosity, brittle
  references, or low-value contributions.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "[--paths=<glob>] [--apply] [--from=<run-dir>] [--budget=strict|default|lax] [--with-history=<N>] [--allow-dirty] [--run-tests] [--no-semantic] [--taxonomy=<path>] [--on-fail=skip|stop|ask]"
  source: "plugins/slop/skills/scan/SKILL.md"
---

# this skill

Repo-wide slop scanner. Audits every tracked file at HEAD for AI slop,
verbose code and comments, fragile hard-coded references, and low-value
contributions. Optionally scans recent history, advisory only. With
`--apply`, each finding becomes its own forward-going commit after the
project's quality gates pass.

The skill never rewrites history. It only adds commits at `HEAD`, so it
is safe on pushed branches and cannot flatten merge topology. For
branch-scoped cleanup with fixups and autosquash, use the `slop-deslop` skill.
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
| `--budget=<level>` | `default` | Tier ceiling; table in `references/detect-pipeline.md` § Budget and confirmation. |
| `--with-history=<N>` | off | Also scan the last N commits' content and messages. Findings are advisory only. N is capped at the commit count, with a warning. |
| `--allow-dirty` | off | Permit a dirty working tree. Dirty files stay advisory; edits, gates, and hooks run in isolation. The apply helper checks the live target before publication. Without the flag, a dirty tree halts at Step 1. |
| `--run-tests` | off | Include the test command in per-commit gates and final verification. |
| `--no-semantic` | off | Skip the Pass B verifier; regex only. |
| `--taxonomy=<path>` | built-in + `.claude/slop.local.yml` | Replace the registry; the built-in set and the override are both ignored. |
| `--on-fail=<mode>` | `skip` | On a per-finding gate failure: `skip` (roll back, mark `gate-failed`, continue), `stop` (roll back, halt), `ask` (surface through `ask-user-choice`). |

## Orchestration Plan

Write the plan per `references/prose-rules.md`.

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in
Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Follow `references/detect-pipeline.md` § Orchestration plan: run
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
No commits yet. Commit the files you want checked, then run slop-scan again.
```

Then check for tracked files:

```console
$ git ls-files | head -n 1
```

If it prints nothing, stop the same way:

```text
No tracked files to scan. Commit the files you want checked, then run slop-scan again.
```

Resolve `BASELINE_SHA` per `references/detect-pipeline.md` §
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

With `--from=<run-dir>`, read the scope, gate commands, and `--on-fail`
from `0000-PLAN.md`. Add its `DIRTY_AT_START` paths to the live dirty
paths; never replace the live list with the saved one. Move findings in
those files to advisory, skip Steps 2 to 8, and go to Step 9.

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

Follow `references/verification-gates.md` § Local gate buckets,
then `references/detect-pipeline.md` § Gate handling. The no-gate
warning says commits will land without gate validation.

## Step 4: Read project tone

Follow `references/detect-pipeline.md` § Tone calibration.

## Step 5: Load the signatures registry

Follow `references/detect-pipeline.md` § Registry load. Registry
source: `references/signatures.yml`.

## Step 6: Detect

Regex first (cheap, deterministic), semantic verification only on
flagged files (expensive, precise).

**Pass A.** Follow `references/detect-pipeline.md` § Pass A.
`<slop_detect.py>` is `references/slop_detect.py`, resolved from this
skill's directory, not the repository root. Resolve it to an absolute
path once, print it, and write that literal path in each command, since
shell variables do not persist between Bash calls. It needs python3 (3.9
or newer).

`<signatures.yml>` is `references/signatures.yml`, resolved and
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

`--out` writes the JSON to the path you give it (see
`references/detect-pipeline.md` § Pass A) and prints counts per tier and signature. Read it with `jq`, not `cat`.

Under `--with-history`, also run the diff and message modes over the
captured log. Their findings carry `historical_only`.

```console
$ git -c core.quotepath=off log -n "<N>" -p HEAD | python3 <slop_detect.py> diff \
    --registry <signatures.yml> \
    --historical \
    --out <history-diff.json>
```

```console
$ git log -n "<N>" -z --format=%H%x1f%B HEAD | python3 <slop_detect.py> messages \
    --registry <signatures.yml> \
    --historical \
    --out <history-messages.json>
```

Each `--out` path is made the same way; read it with `jq`. Then run the Guard
check from the pipeline reference. A finding has `{file, line_start,
signature_id, tier, confidence: regex, action, historical_only}`. A finding with `historical_only: true` is advisory at
any tier, because the skill cannot edit historical commits. A finding in
a file listed in `DIRTY_AT_START` is advisory too.

**Pass B.** Follow `references/detect-pipeline.md` § Pass B with a
file as the unit. Pass the file's full content; replacement text follows
`references/prose-rules.md`.

## Step 7: Apply tiers, budget, and grouping

Apply `references/detect-pipeline.md` § Budget and confirmation,
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
findings. For aggregation, use the `slop-deslop` skill.

## Step 8: Materialize the patch series

Always materialize first; the series is the user's review surface.
Create the run directory per `references/detect-pipeline.md` §
Run directory, with `<name>` = `slop-scan`. Cut patches in list order
using that reference's § Cut patches, so each patch sees earlier edits.

Layout:

```
<run-dir>/
├── 0000-PLAN.md                       (plan + registry source path + SHA-256)
├── NNNN-edit-<file-slug>-<sigid>.patch
├── advisory.md                        (Tier C, over-budget, declined, historical-only, dirty-file findings)
├── gates.json                         (approved gate names and shell commands)
└── commits.json                       (finding → proposed commit subject + body)
```

`0000-PLAN.md` adds `START_SHA`, the scope's file count, the `--on-fail`
mode, and `DIRTY_AT_START` to the fields in § Run directory.

`commits.json` is a list in apply order. Each entry holds `patch`, `file`,
`signature_id`, and the proposed `subject` and `why:` / `what:` `body`,
built from `references/commit-template.md` and written per
`references/prose-rules.md`. The user may edit an entry or delete
one to skip it, then re-invoke with `--apply --from=<run-dir>`; the loop
reads the file as it stands. A re-invocation without `--from` detects
again, writes a new run directory, and ignores those edits. Do not reorder
the list during apply; a stale patch fails safely in the scratch worktree.

Write `gates.json` as a JSON list of objects with string `name` and
`command` fields, in format, lint, typecheck, test order. Commands run
from an isolated repository root against committed files. Omit empty
buckets and tests unless `--run-tests` was passed. With no gates, write
`[]` and retain the no-gate warning. A missing dependency is a gate
failure; never install dependencies or fall back to the user's checkout.

Without `--apply`, print the Step 11 report (skip its git and gate
commands; committed and gate-failed counts are 0) and stop.
The user re-invokes with `--apply --from=<run-dir>` once the proposals
look right.

## Step 9: Confirmation gate

Reached only with `--apply`. Follow
`references/detect-pipeline.md` § Confirmation gate with these
choices:

| Choice | Effect |
|---|---|
| **Patches only** (default) | Nothing is applied. |
| **Apply and commit** | Run the per-finding commit loop. |
| **Cancel** | Delete `<run-dir>/` and exit. |

Headless, the printed command is the `--apply --from=<run-dir>` re-run. "Apply and
commit" approves **Apply and commit** and nothing broader: no push.

## Step 10: Per-finding commit loop

`<scan_apply.py>` is `references/scan_apply.py`, resolved from this
skill's directory to an absolute path written literally in each command.
It requires python3 3.9 or newer. Review messages against
`references/prose-rules.md` before applying: no AI trailers or emoji.

Take `commits.json` in list order. Start `<expected-head>` at `START_SHA`;
after each successful commit, use the helper's returned `commit` as the
next expected head. `<entry>` is the zero-based list index:

```console
$ python3 <scan_apply.py> \
    --run-dir "<run-dir>" \
    --expected-head "<expected-head>" \
    --entry <entry>
```

Add `--allow-dirty` only when the user passed it. The helper applies the
patch, runs gates, and commits with hooks in a disposable worktree. It
then verifies that only the approved file changed, checks the live
branch and target again, and publishes that file while preserving the
user's index. It never restores or cleans the user's other paths.
If hooks change the gated content, it checks the exact candidate in a
fresh worktree before publication; a formatter edit there rejects it.

Read its JSON status:

- `committed`: record the returned commit.
- `no-op`: record the finding as already fixed; no commit was created.
- `gate-failed` or `hook-failed`: record stderr. `--on-fail=skip`
  continues; `stop` halts; `ask` offers correcting the patch and retrying,
  skipping, or stopping. Without a question tool, `ask` means `skip`.
- `refused` or `recovery-needed`: halt and report the reason and any
  `recovery_branch`. Inspect the live state before retrying. Never reset
  or clean it to force the series through.

Gate and hook failures discard only the isolated attempt. The original
checkout keeps its staged, unstaged, and untracked work.

## Step 11: Final verification and report

Write the report per `references/prose-rules.md`.

```console
$ git log --oneline "<START_SHA>..HEAD"
```

```console
$ git status --porcelain
```

Verify the final tip in isolation, adding `--allow-dirty` only when the
user passed it:

```console
$ python3 <scan_apply.py> \
    --run-dir "<run-dir>" \
    --expected-head "<expected-head>" \
    --verify
```

Report `gate-failed` or `gate-modified` as a failed final gate. The JSON
names the command, output, and files requiring attention. Keep those
findings open; the helper never copies final-gate edits into the checkout.

The hero line is `Slop scan summary`; sections follow in the order
shown: summary block, `Open findings`, `Quality gates (final)`,
`Per-finding commits`, `Gate-failed findings`, then the `Patch series:`
line. `Open findings` lists each Tier A and B finding neither committed nor gate-failed as
`signature_id file:line` (`signature_id <short-sha> subject` or `body`
for a history finding), at most 10, then `and N more`; omit it when none
remain. A precondition refusal prints one sentence naming the cause,
then what the user must do. An attempted apply uses the summary even
when `--on-fail=stop` halted it. Under `Gate-failed findings`, name the
failure, whether the checkout was preserved, and the required next step.
Do not add process or rule-compliance commentary.

Print only this report, starting literally with `Slop scan summary`.
Use plain text outside a code fence and plain bullets: no preamble,
recap, bold labels, or extra sections. Omit local paths except the
patch-series path and commands that use it:

```text
Slop scan summary
=================
Scope: 42 files (paths: src/**, docs/**)
Budget: default
Findings: 5 (2 Tier A, 2 Tier B, 1 Tier C, 0 historical-only)

Committed: 3
Gate-failed: 1
Hook-failed: 0
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

Print `Next: git push` only after commits landed; after an audit or a
zero-commit run print the `--apply --from=<run-dir>` re-run instead.

`Patch series:` carries the path Step 8 printed; the user reviews
`commits.json` and `advisory.md` there. Do not push; no history
changed, so a plain `git push` suffices.

End with the next step, through `ask-user-choice` when available,
otherwise as a plain line: after an audit, the `--apply --from=<run-dir>` re-run; after
commits, `git push`.

## Edge cases

Read `references/scan-edge-cases.md` for the per-case behavior
(empty repo, dirty files, binary files, and similar).


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
