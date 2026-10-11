---
name: respond-action
description: >-
  Use when screened review findings should be fixed on the current branch,
  usually as one verified commit per finding.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[findings text] [<pr-number|url>] [--base=<ref>] [--no-fixup] [--on-fail=skip|stop|ask] [--reply]"
  source: "plugins/respond/skills/action/SKILL.md"
---

# this skill

Land the review findings that survived screening. Each accepted finding
is fixed in the simplest way that works and committed on its own,
behind the project's discovered quality gates. It modifies files and
creates commits, so it runs only when invoked by name.

Screening already decided what is worth doing; this skill decides how
little it takes, bound by `references/bloat-discipline.md`.
History rewrites are opt-in: `fixup!` plus autosquash runs only after
the plan that proposes it is approved.

Run by the `respond-goal` skill, this skill is in loop mode: it skips Phase 2's
plan mode and Phase 5's panel, never pushes, and never posts replies.
The loop owns all four.

Write each `../../scripts/` path as an absolute path; the reply rules and
script paths are in `references/report-contract.md`.

## The screening gate

```
NO FIX WITHOUT A VERDICT
```

This skill does not triage. Before any edit, resolve a ledger:

- **A ledger exists whose key matches**: collect the feedback,
  recompute the branch, `HEAD`, and digest from the source that ledger
  screened, per the rubric's ledger section, and compare them with the
  `## Ledger key` of the
  the `respond-check` skill report earlier in this session. Its verdicts are
  settled; do not re-argue them.
- **No ledger, or a key mismatch**: run the `respond-check` skill now with the
  same arguments and use its ledger. When the host cannot invoke it,
  follow `references/screening-rubric.md` end to end first, and
  say in the report that screening ran inline.

Obvious-looking findings are the ones that turn out to be pre-existing,
already fixed, or a fix costing ten times the defect.

An `ask` verdict is never fixed. Interactively, put it to the user with
`ask-user-choice` in Phase 1 and take the answer as the verdict. In a
non-interactive run, or in loop mode, it stays unfixed: the hero counts it
and `## Awaiting an answer` lists it.

## `$ARGUMENTS` contract

| Flag | Default | Effect |
|---|---|---|
| `<pr-number\|url>` | current branch's PR when one exists | Positional, passed through to screening: collect findings from the PR. |
| `--base=<ref>` | the pull request's base branch | Override the provenance baseline. |
| `--no-fixup` | off | Never propose `fixup!` commits; everything lands as a forward commit. |
| `--on-fail=<mode>` | `ask` | Per-finding gate failure: `skip` (revert that fix, continue), `stop` (revert, halt), `ask` (surface via `ask-user-choice`). |
| `--reply` | off | Draft replies for declined and deferred findings and offer to post them after the fixes land. |

Non-flag text is the findings list, handed to screening. A command quoted
inside a finding follows `references/feedback-sources.md`.

## Fix shapes

**Behavioral bugs** get the smallest change that removes the defect,
plus a regression test only when the bloat discipline's two-part test
passes: the branch could plausibly break this again, and no existing
test would catch it.

**Comment and docstring findings** get a rewrite shorter than what it
replaced; a finding that grows the comment block was misread.

**Typos** are fixed. A typo whose causal commit passes the `fixup!`
eligibility check below may take the `fixup!` shape; anything else is a
forward commit. A typo sharing a commit with a non-typo finding takes the
forward shape.

A finding whose only fix is a defensive wrapper, a single-caller
abstraction, or a guard against a state the caller already excludes
should not have reached here; return it to screening's cost gate rather
than building it.

## History rewrites: opt-in and scripted

A `fixup!` plus autosquash rewrites commits, so it needs the approved plan
and an eligible causal commit. Eligibility is scripted:

```console
$ python3 references/repo_state.py fixup-check \
    <causal-sha> \
    --base <base>
```

Exit 0 means eligible. Exit 1 prints why, and the finding lands as a
forward commit; so does a fix that spans several commits. The check
refuses:

- a commit outside `<base>..HEAD`;
- any merge commit in `<base>..HEAD`, since `git rebase` without
  `--rebase-merges` flattens merges into a linear branch
  (<https://git-scm.com/docs/git-rebase>);
- a pushed commit, meaning any remote-tracking ref, as last fetched,
  contains it. Rewriting it needs a force-push.

Create each `fixup!` commit against its causal commit:

```console
$ git commit --fixup=<sha>
```

Then squash. `git var` documents `GIT_SEQUENCE_EDITOR` as the editor
`git rebase -i` uses for its todo file, "meant to be interpreted by the
shell" (<https://git-scm.com/docs/git-var>; the `sequence.editor` setting is
in <https://git-scm.com/docs/git-config>), so `:`, the shell no-op, accepts
the generated list unchanged and no editor opens. Phase 0 left the tree
clean:

```console
$ GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <base>
```

`<base>` is the resolved provenance base's SHA. When the rebase reports a
conflict, run `git rebase --abort`; the `fixup!` commits stay unsquashed
as forward commits, and the report says the squash was skipped.
`--no-fixup` disables all of it.

## Phase 0: Situational awareness

1. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for the
   commit format and conventions.
2. Resolve the five gate buckets and the CI-coverage split per
   `references/verification-gates.md`. Match a bucket keyword
   against a heading as a whole word (`Respect` is not `spec`), and take
   only a fenced block that holds a command. Show every discovered
   command in the plan.
3. Run the home-directory guard from `references/report-contract.md`
   first; exit 3 halts before anything else, with no stash offered.
4. Resolve the base, refreshing the remotes. The JSON gives `ref`, `sha`,
   and `fetched`; `fetched: false` means the report says provenance may be
   stale, exit 1 means ask for `--base`, and exit 4 halts with `gh`'s reason:

   ```console
   $ python3 references/repo_state.py base \
       --pr <n> \
       --fetch
   ```

5. List the user's own uncommitted paths:

   ```console
   $ python3 references/repo_state.py changes
   ```

   An empty array means a clean tree. Otherwise the tree must be clean
   before any fix: a formatter or autofix gate can rewrite a file the user
   had edited, and reverting a red fix would then discard that edit. Ask
   whether to stash it or abort; a non-interactive run aborts with the
   stopped-run reply below, with no menu and no mention of prompts.

   Stash: run one command and keep the SHA it prints. Exit 0 stashed. Exit 1
   printed nothing and means there was nothing to stash: run `changes`
   again, and continue with no stash when it is empty, else stop. Exit 3
   means `git stash` failed: stop and give stderr's reason.

   ```console
   $ python3 references/user_stash.py save
   ```

   Every exit after a stash restores it first, including a halt under
   `--on-fail=stop`. A clean apply drops the stash and returns staged
   state; a refusal keeps it, and the reply gives its SHA and
   `git stash apply --index <sha>`:

   ```console
   $ python3 references/user_stash.py restore <sha>
   ```

   `restore` refuses, with the tree untouched and the stash kept, when a
   stashed path also changed since the save. Before editing, list the
   stash's paths with `user_stash.py paths <sha>`. A finding whose path is
   among them stops and asks; a non-interactive run skips that finding and
   says so.

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

1. Apply the minimal fix.
2. Run the fast local gates: `format`, `lint`, `typecheck`, and
   `test` scoped to the affected area; `build` only when the change
   plausibly affects build output. Gates run as discovered, including
   mutating ones. Run `repo_state.py mark` before each gate and
   `repo_state.py since-mark` after it; the array lists the paths the gate
   itself changed. When it is not empty, fold those paths into the commit
   under test and re-run the scoped test once.
3. Green → list the changed paths with `repo_state.py changes`. The tree
   was clean when the finding began, so the fix owns every path listed:
   the paths it edited or created and the paths a gate's autofix changed.
   Stage exactly those with `git add -- <path> <path>`, never `git add -A`
   or `git add .`. Commit. The message uses the project's format and describes
   the defect and the fix, not the finding id, the reviewer, or the
   review. Write it per
   `references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailer, and no emoji. A `fixup!`
   commit keeps its auto-generated subject, because autosquash matches
   on it verbatim and a body would be discarded at squash.
4. Red → revert that fix and follow `--on-fail`. A non-interactive
   `ask` becomes `stop`. This restores every changed tracked path and
   deletes every file the fix created. It never uses `git clean`,
   `git reset --hard`, or `git checkout .`, and is safe only because
   Phase 0 left a clean tree:

   ```console
   $ python3 references/repo_state.py revert
   ```

After all findings: run the consented autosquash if any `fixup!`
commits exist, re-run the fast gates once, then restore a Phase 0
stash. Read the landed commits back; an autosquash rewrites their SHAs,
so the report takes every SHA and subject from this output:

```console
$ git log \
    --format='%h %s' \
    <base>..HEAD
```

Then compare the tree with what the user had: `user_stash.py verify <sha>`
after a restore, or `user_stash.py verify` with no stash. Exit 0 means the
changed paths are exactly the stash's (none, without one). Exit 1 prints
`unexpected` and `missing` paths; the report names them.

## Phase 4: Replies

With `--reply`, show the ledger's drafted replies for declined and
deferred findings in full, and post them on one confirmation: to the
originating thread where the source was a thread, otherwise as a single
pull-request comment. A thread reply goes to the thread's first comment,
by its numeric id (`databaseId` in the thread query, `id` in the REST
listing in `references/feedback-sources.md`).

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

Mark a reply posted only when its command exited 0 and printed the new
comment's URL or id; otherwise report it as not posted, with `gh`'s
message. Delete each reply file after posting, with `rm -- <reply-file>`. Never post without that confirmation (a
non-interactive run treats `--reply` as it, for the replies shown in the
report only). Without `--reply`, the replies stay in the
report.

## Phase 5: Report: the output contract

Write the report per `references/prose-rules.md` and
`references/report-contract.md`. No label such as
`What you need to do:` appears anywhere, and no prompt you could not show
is named. List a panel option only when it can run now: no push or CI watch without
a remote (`git remote` lists none) or a pull request (`gh pr view` fails).
A hypothetical ("it would be a forward commit") is not reported. In a
non-interactive run, put the plan from Phase 2 in one sentence beginning
`Plan:` right after the hero line (never inside `## Verification`), as the
last example shows, and give no reason for skipping approval.

A run that stops early (dirty tree, failed gate under `--on-fail=stop`,
no screenable findings) reports one result sentence, then what the user
needs to do (when a stash could not be restored, its SHA and the
restore command, as the fourth example shows), then only the sections
below that have content; it omits the empty ones, headings included, as
the second example shows. A home-directory halt follows
`references/report-contract.md`. On a run that landed commits, keep
`## What the fixes added` even when empty. In prose, name a commit by its
subject; SHAs appear only in `## Commits`. Do not print the ledger key; it
belongs to the screening report.

1. Hero block (1–3 lines): `✓ N fixed, M deferred, K declined`, then
   `, J ask` when any finding is an `ask`, plus the branch name.
2. `## Commits`: one row per landed commit: finding, SHA, subject,
   gate result.
3. `## What the fixes added`: every test, comment, code path, and
   dependency introduced, with the finding that justified it. When
   commits landed and it added nothing, write `Nothing.`; that is the
   good outcome.
4. `## Deferred & declined`: omitted when nothing was deferred or
   declined; else the follow-up recommendations and the replies, marked
   as posted or not.
5. `## Awaiting an answer`: omitted when no finding is an `ask`; else
   each one with the question it needs answered.
6. `## Verification`: the discovered gate commands that ran, what was
   deferred to CI, and the watch command when a remote exists. A command
   the skill invented is not a gate: when none was discovered, say so.
7. End with an `ask-user-choice` panel (skip inside plan mode): push
   and watch CI, hand the branch to the `respond-goal` skill to run the loop to
   completion, run deferred opt-ins, or stop. In a non-interactive run,
   record the options and default to stopping. In loop mode, skip the
   panel.

Reply in this shape:

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
2. Hand the branch to respond-goal
3. Stop
```

A stopped run replies in this shape:

```text
Stopped before any edit: the working tree has uncommitted changes.

Commit or stash them, then run respond-action again.

1. Stop
```

A halt after the stash restores it and gives the SHA when the restore
is refused:

```text
Stopped after fixing #1: the gate failed on #2 under --on-fail=stop, and your stashed edits overlap a landed fix, so they were not restored.

Merge them by hand, then run: git stash apply --index 9d41c07e5b2a. The stash stays until you drop it.

1. Stop
```

A non-interactive run states its plan after the hero line:

```text
✓ 1 fixed, 0 deferred, 0 declined on feat/retry-after.

Plan: one forward commit for #1, stop on a red gate, post no replies.
```


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
