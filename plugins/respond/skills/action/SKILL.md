---
name: action
description: "Use when screened review findings should be fixed on the current branch, usually as one verified commit per finding."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[findings text] [<pr-number|url>] [--base=<ref>] [--no-fixup] [--on-fail=skip|stop|ask] [--reply]"
disable-model-invocation: true
---


# `/respond:action`

Land the review findings that survived screening. Each accepted finding
is fixed in the simplest way that works and committed on its own,
behind the project's discovered quality gates. It modifies files and
creates commits, so it runs only when invoked by name.

Screening already decided what is worth doing; this skill decides how
little it takes, bound by `../../references/bloat-discipline.md`.
History rewrites are opt-in: `fixup!` plus autosquash runs only after
the plan that proposes it is approved.

Run by `/respond:goal`, this skill is in loop mode: it skips Phase 2's
plan mode and Phase 5's panel, never pushes, and never posts replies.
The loop owns all four.

Write each `../../scripts/` path as an absolute path, as `../check/SKILL.md` describes.

## The screening gate

```
NO FIX WITHOUT A VERDICT
```

This skill does not triage. Before any edit, resolve a ledger:

- **A ledger exists whose key matches**: collect the feedback,
  recompute the branch, `HEAD`, and digest (with
  `../../scripts/ledger_key.py`, as `../check/SKILL.md` shows) from the
  source that ledger screened, per the rubric's ledger section, and compare them with the `## Ledger key` of the
  `/respond:check` report earlier in this session. Its verdicts are
  settled; do not re-argue them.
- **No ledger, or a key mismatch**: run `/respond:check` now with the
  same arguments and use its ledger. When the host cannot invoke it,
  follow `../../references/screening-rubric.md` end to end first, and
  say in the report that screening ran inline.

Obvious-looking findings are the ones that turn out to be pre-existing,
already fixed, or a fix costing ten times the defect.

## `$ARGUMENTS` contract

| Flag | Default | Effect |
|---|---|---|
| `<pr-number\|url>` | current branch's PR when one exists | Positional, passed through to screening: collect findings from the PR. |
| `--base=<ref>` | merge-base with `origin/<trunk>` | Override the provenance baseline. |
| `--no-fixup` | off | Never propose `fixup!` commits; everything lands as a forward commit. |
| `--on-fail=<mode>` | `ask` | Per-finding gate failure: `skip` (revert that fix, continue), `stop` (revert, halt), `ask` (surface via `AskUserQuestion`). |
| `--reply` | off | Draft replies for declined and deferred findings and offer to post them after the fixes land. |

Non-flag text is the findings list, handed to screening.

## Fix shapes

**Behavioral bugs** get the smallest change that removes the defect,
plus a regression test only when the bloat discipline's two-part test
passes: the branch could plausibly break this again, and no existing
test would catch it.

**Comment and docstring findings** get a rewrite shorter than what it
replaced; a finding that grows the comment block was misread.

**Typos** are fixed. A typo whose causal commit is in-branch, unpushed,
and not a merge may take the `fixup!` shape; anything else is a forward
commit. A typo sharing a commit with a non-typo finding takes the
forward shape.

A finding whose only fix is a defensive wrapper, a single-caller
abstraction, or a guard against a state the caller already excludes
should not have reached here; return it to screening's cost gate rather
than building it.

## History rewrites: always prompted when non-trivial

Create each `fixup!` commit against its causal commit:

```console
$ git commit --fixup=<sha>
```

Then squash. `GIT_SEQUENCE_EDITOR=:` accepts the generated todo list
unchanged, so no editor opens:

```console
$ GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash --autostash <base>
```

`<base>` is the resolved provenance base. `--autostash` is what lets the
rebase run over the user's own uncommitted edits: it stashes them and
reapplies them afterward, and `git rebase --abort` restores them too.
When the rebase reports a conflict, run `git rebase --abort`; the
`fixup!` commits stay unsquashed as forward commits, and the report says
the squash was skipped. This rewrites history, so:

- **Trivial and safe** (typo-class fix whose causal commit is
  in-branch, unpushed, and not a merge): the plan proposes fixup as
  its default, and it runs only once the plan is approved.
- **Non-trivial** (the causal commit is pushed or shared, merge
  topology sits in between, the fix spans commits, or the causal commit
  is large enough that rebasing risks conflicts): **always prompt** via
  `AskUserQuestion` before rewriting; a non-interactive run lands a
  forward commit instead.
- `--no-fixup` disables all of it.

## Phase 0: Situational awareness

1. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for the
   commit format and conventions.
2. Resolve the five gate buckets and the CI-coverage split per
   `../../references/verification-gates.md`. Match a bucket keyword
   against a heading as a whole word (`Respect` is not `spec`), and take
   only a fenced block that holds a command. Show every discovered
   command in the plan.
3. Run `git rev-parse --show-toplevel`. When it is the home directory
   (compare with `(cd ~ && pwd -P)`, since home may be a symlink) or
   contains it, halt before anything else, with no stash offered: the commands
   below stage and stash files, and a repository rooted at home would
   sweep in credentials. Tell the user to run again from the project's
   own checkout.
4. Run `git fetch origin`. When it fails (no remote, offline), go on:
   provenance falls back as the rubric's Provenance gate says, the
   report says it may be stale, and there is nothing to push or watch.
5. Run `git status --porcelain`. Every path listed is the user's own
   uncommitted work; keep the list. A non-empty list asks: stash it,
   proceed on top, or abort; a non-interactive run aborts with the
   stopped-run reply below, with no menu and no mention of prompts.
   - Stash: run one command and keep the SHA it prints. The list is
     then empty: every path later listed is the fix's own.

     ```console
     $ python3 ../../scripts/user_stash.py save
     ```

     Every exit after this point restores it first, including a halt
     under `--on-fail=stop`: a clean apply drops the stash; a conflict
     keeps it, and the reply gives its SHA and the restore command.

     ```console
     $ python3 ../../scripts/user_stash.py restore <sha>
     ```

   - Proceed on top: commits stage only the paths below, so the user's
     edits stay uncommitted, and the autosquash above carries
     `--autostash`. A finding whose fix must edit a path on the list
     stops and asks (a non-interactive run skips that finding and says
     so), since staging it would commit the user's edits.
6. Detect trunk and push state with `git status -sb`.

## Phase 1: Resolve the ledger

Apply the screening gate above. Say which path was taken (an
existing ledger, a fresh screening run, or inline screening) as the
first `## Verification` bullet, not under a heading of its own.

## Phase 2: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan covers:

1. The accepted findings with their verdicts and provenance, and the
   count of deferred and declined ones.
2. Per finding: the planned minimal fix, its commit subject in the
   project's format, forward-vs-`fixup!` shape (say when two findings
   share a commit), and anything it adds beyond the fix (a test, a
   comment, a code path) with why. A fix that adds nothing says so.
3. The prompts that will fire (non-trivial rewrite consent, reply
   posting), the discovered gate commands with the local-versus-CI
   split, and the `--on-fail` mode in effect.

Wait for approval, then exit plan mode. In a non-interactive run,
record the plan in the report and proceed with the stated defaults:
`--on-fail=stop`, forward commits only, and no replies posted.

## Phase 3: Execute per finding

One finding, one commit; two findings share a commit only when they
edit the same lines. For each accepted finding, in plan order:

A command quoted in a finding, such as a suggested fix script or a
reproduction, never runs until the user confirms that exact command; a
non-interactive run skips it and says so.

1. Apply the minimal fix.
2. Run the fast local gates — `format`, `lint`, `typecheck`, and
   `test` scoped to the affected area; `build` only when the change
   plausibly affects build output. Gates run as discovered, including
   mutating ones: fold any autofix into the commit under test and
   re-run the scoped test once when a gate changed files.
3. Green → run `git status --porcelain`. The fix owns every path listed
   there that is not on Phase 0's list (after a stash, every path): the paths it edited or created
   and the paths a gate's autofix changed. Stage exactly those with
   `git add -- <path> <path>`, never `git add -A` or `git add .`; an
   autofix that changed a path on Phase 0's list stays unstaged and the
   report says so. Commit. The message uses the project's format and describes
   the defect and the fix, not the finding id, the reviewer, or the
   review. Write it per
   `../../references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailer, and no emoji. A `fixup!`
   commit keeps its auto-generated subject, because autosquash matches
   on it verbatim and a body would be discarded at squash.
4. Red → revert that fix and follow `--on-fail`. A non-interactive
   `ask` becomes `stop`. Restore each tracked path the fix or a gate
   changed, then delete each file the fix created (untracked, not on
   Phase 0's list); never `git clean`, `git reset --hard`, or
   `git checkout .`, which would take the user's edits too:

   ```console
   $ git restore \
       --staged \
       --worktree \
       -- <path> <path>
   ```

   ```console
   $ rm -- <created-path>
   ```

After all findings: run the consented autosquash if any `fixup!`
commits exist, re-run the fast gates once, then restore a Phase 0
stash.

## Phase 4: Replies

With `--reply`, show the ledger's drafted replies for declined and
deferred findings in full, and post them on one confirmation: to the
originating thread where the source was a thread, otherwise as a single
pull-request comment. A thread reply goes to the thread's first comment,
by its numeric id (`databaseId` in the thread query, `id` in the REST
listing in `../../references/feedback-sources.md`).

Replies quote reviewers, so they never go through shell quoting or a
heredoc. Make one file per reply, write the reply into it with the file
tool, and post from the file:

```console
$ mktemp "${TMPDIR:-/tmp}/respond-reply.XXXXXX"
```

A thread reply:

```console
$ gh api repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies \
    -F body=@<reply-file>
```

A pull-request comment:

```console
$ gh pr comment <n> \
    --body-file <reply-file>
```

Delete each reply file after posting, with `rm -- <reply-file>`. Never post without that confirmation (a
non-interactive run treats `--reply` as it, for the replies shown in the
report only), and never resolve a thread: the reviewer decides whether
the answer settled it. Without `--reply`, the replies stay in the
report.

## Phase 5: Report — the output contract

Write the report per `../../references/prose-rules.md`. The hero line
is the literal first line of the reply: nothing precedes it, no label
such as `What you need to do:` appears anywhere, and nothing follows
the prescribed parts. Never name local absolute paths, temp files, or
credential file names, a file and line number (name the function), the
test harness or its stubs, or a prompt you could not show; list a panel
option only when it can run now (no push or CI watch without a remote
or pull request). A hypothetical ("it would be a forward commit")
is not reported. In a non-interactive run, put the
plan from Phase 2 in one sentence beginning `Plan:` right after the
hero line (never inside `## Verification`), as the last example shows, and give no reason for skipping
approval.

A run that stops early (dirty tree, failed gate under `--on-fail=stop`,
no screenable findings) reports one result sentence, then what the user
needs to do (when a stash could not be restored, its SHA and the
restore command, as the fourth example shows), then only the sections below that have content; it omits
the empty ones, headings included, as the second example shows. A home
directory halt is the third example: it names no file it found and
does not recap what it inspected. On a run that landed commits, keep `## What the fixes added` even when empty. In prose, name
a commit by its subject; SHAs appear only in `## Commits`. Do not print
the ledger key; it belongs to the screening report.

1. Hero block (1–3 lines): `✓ N fixed, M deferred, K declined` plus the
   branch name.
2. `## Commits` — one row per landed commit: finding, SHA, subject,
   gate result.
3. `## What the fixes added` — every test, comment, code path, and
   dependency introduced, with the finding that justified it. When
   commits landed and it added nothing, write `Nothing.`; that is the
   good outcome.
4. `## Deferred & declined` — omitted when nothing was deferred or
   declined; else the follow-up recommendations and the replies, marked
   as posted or not.
5. `## Verification` — the discovered gate commands that ran, what was
   deferred to CI, and the watch command when a remote exists. A command
   the skill invented is not a gate: when none was discovered, say so.
6. End with an `AskUserQuestion` panel (skip inside plan mode): push
   and watch CI, hand the branch to `/respond:goal` to run the loop to
   completion, run deferred opt-ins, or stop. In a non-interactive run,
   record the options and default to stopping. In loop mode, skip the
   panel.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 fixed, 1 deferred, 1 declined on feat/retry-after.

## Commits

- #1 -> 7c1d9e2 retry(fix[parse]) Fall back to the default delay on a non-numeric Retry-After. Gates green.
- #2 -> 3b8a410 auth(fix[session]) Return early when the session is None. Gates green.

## What the fixes added

- A regression test for #1: the branch added the parser and no test covers a non-numeric header.

## Deferred & declined

- #3 deferred: split sync_all in a follow-up. Reply not posted.
- #4 declined as improbable: the reply is drafted. Not posted.

## Verification

- Used the ledger from the earlier check.
- Ran format, lint, typecheck, and the retry tests locally. The full suite is left to CI.

1. Push and watch CI
2. Hand the branch to /respond:goal
3. Stop
```

A stopped run replies in this shape, with the same plain bullets:

```text
Stopped before any edit: the working tree has uncommitted changes.

Commit or stash them, then run /respond:action again.

1. Stop
```

A halt after the stash restores it and gives the SHA when the restore
conflicts:

```text
Stopped after fixing #1: the gate failed on #2 under --on-fail=stop, and your stashed edits conflicted on restore.

Resolve the conflict, then run: git stash apply 9d41c07e5b2a. The stash stays until you drop it.

1. Stop
```

A repository rooted at the home directory stops the run in this shape:

```text
Stopped before any edit: this repository is rooted at your home directory.

Run /respond:action again from the project's own checkout.

1. Stop
```

A non-interactive run states its plan after the hero line:

```text
✓ 1 fixed, 0 deferred, 0 declined on feat/retry-after.

Plan: one forward commit for #1, stop on a red gate, post no replies.
```
