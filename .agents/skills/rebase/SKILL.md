---
name: rebase
description: >-
  Use when a user explicitly wants to rebase a branch onto remote trunk,
  check file overlap, and resolve conflicts while keeping local edits.
allowed-tools: ["Bash", "Read", "Edit", "AskUserQuestion"]
metadata:
  source: "plugins/rebase/skills/rebase/SKILL.md"
---

## Task

Rebase the current branch onto remote trunk, preserve local edits and their
staging, verify the replay, and report recovery choices. Never push.

`<replay>` is `references/replay.py`, resolved from this skill's directory
to an absolute path written literally in each command. Run it with `python3`.
It prints JSON containing `ok`, `phase`, and exact recovery refs. Keep those
values across tool calls; shell variables do not persist. The helper owns
the rebase and stash commands, including continuation and restoration.

Write reports and any authorized commit message per
`references/prose-rules.md`.

### Phase 1: Inspect the repository and detect trunk

1. Require Git 2.36 or newer and Python 3.9 or newer. Stop if either is absent.
2. Read the branch, `git status --short`, and remotes. Stop outside a
   repository, on detached HEAD, or without a remote. Record staged and
   unstaged paths separately so final verification can check both.
3. Stop if a rebase, merge, cherry-pick, or revert is already in progress.
   `git rev-parse --git-path <marker>` always prints a path; check whether
   that path exists. The rebase markers are `rebase-merge` and `rebase-apply`.
4. Read the project's AGENTS.md / CLAUDE.md for verification commands.

Choose the remote that carries trunk. Use the only remote when there is one.
Otherwise use `upstream` when it exists alongside a different tracking
remote, then the tracking remote, then `origin`. A tracking remote of `.`
means a local branch, not a fetch remote. If the choice remains unclear,
ask; without a question tool, stop and name the choice required.

Ask the selected remote for its default branch:

```console
$ git ls-remote --symref <remote> HEAD
```

The `ref:` line names `refs/heads/<trunk>`. If that query fails, inspect
`refs/remotes/<remote>/HEAD`, then existing `<remote>/main` or
`<remote>/master` refs. Stop when none resolves. Stop on the trunk branch
itself. Use literal remote and branch names in subsequent commands.

### Phase 2: Fetch and analyze

Fetch the selected remote. A failed fetch stops the operation; do not replay
against an unverified stale target.

```console
$ git fetch <remote>
```

Inspect the proposed replay:

```console
$ python3 <replay> inspect \
    --onto <remote>/<trunk>
```

The helper refuses merge commits, unrelated histories, existing operations,
and untracked or ignored files that a replay could overwrite. It also stops
when the branch is already current or only needs a fast-forward. For a
fast-forward, print `git merge --ff-only <remote>/<trunk>` for the user.

Use `base`, `tip`, and `target_oid` from the result to read the branch commits
and both sides of each path in `overlap`. An empty overlap list needs no
file-specific diff. Describe expected conflicts as an estimate; rebasing
replays each commit, so even disjoint final changes can conflict.
Keep the overlap paths for the final report, including paths that replay
without a conflict.

### Phase 3: Execute

The user's request to rebase authorizes this step. Run:

```console
$ python3 <replay> start \
    --onto <remote>/<trunk>
```

Before replay, the helper creates a backup branch, saves tracked local edits
with their index, and pins their exact stash object. Untracked and ignored
files stay in place unless they overlap replayed paths, which stops the run.
It pins the fetched target and prevents `rebase.updateRefs` from moving other
branches. It runs the configured pre-rebase hook once, then rechecks for hook
edits, commits, and collisions before replay. Other hooks and signing remain
enabled. If a hook changes the branch, preserve its new work and ask the user
how to proceed; do not reset it back to the backup.

Read the returned state:

- `complete`: go to Phase 5. `outcome` distinguishes a completed replay from
  a failed attempt restored to the original branch.
- `rebase_conflict`: go to Phase 4. The backup and saved edits remain pinned.
- `restore_conflict` or `restore_blocked`: the replay may be finished, but
  restoring saved edits needs attention; follow Phase 5.
- Any other failure: stop with its actual reason and recovery refs. Do not
  reset, clean, or start a second rebase to recover from it.

If a hook or signing prompt blocks, interrupt that process and report the
recorded state. Do not automatically abort through edits made during replay.

### Phase 4: Resolve replay conflicts

Read `git status` and each conflicted file. Compare the branch's intended
change with trunk. Resolve mechanical conflicts, such as adjacent additions
or renamed context, by retaining both intended changes. Competing behaviors
need the user's choice. Without a question tool, leave the conflict intact
and report both choices; never silently pick a side or abort.
Describe only the existing behaviors, in plain words with no code literals
(say "a list holding one empty string", not `[""]`). Do not propose a
combined behavior, replacement expression or patch before the user chooses.

Stage only resolved files with `git add -- <file>`, then continue through the
helper:

```console
$ python3 <replay> continue
```

It verifies that this is the recorded rebase, rejects unrelated staged work
and new collisions, disables interactive commit-message editing, and restores
the saved index only after replay finishes. Repeat for additional conflicts.
Do not run quality checks while replay is unresolved.

If the user explicitly chooses to abort, preserve any new resolution work
first, run `git rebase --abort`, then restore the original saved edits:

```console
$ python3 <replay> restore
```

### Phase 5: Verify the replay and saved edits

1. Read the helper's outcome and `git status`. Compare restored staged and
   unstaged paths with the starting state. A successful restore keeps the
   user's staging and all edits uncommitted.
2. For `restore_conflict`, name the affected files and the exact `stash` SHA.
   The rebase is finished when `outcome` is `rebased`; never abort it then.
   Resolve mechanical conflicts only. Competing meanings require the user's
   choice; headless runs leave them intact. The original staged snapshot is
   `<stash>^2`, and the original working snapshot is `<stash>`. Preserve the
   staging of local edits the user keeps. After the user chooses, verify the
   result with `git status` instead of assuming the file must remain dirty.
   Never unstage every file.
3. For `restore_blocked`, new hook or user edits prevented stash application.
   Keep both versions. After the user preserves those new edits, `restore`
   retries against a clean tracked state without overlapping untracked or
   ignored files. It applies the recorded stash,
   regardless of changes to the global stash stack.
4. After manually combining a blocked or conflicted restoration, acknowledge
   it with `restore --resolved`. This checks for unresolved index entries
   and changes no files or staging. Never drop, pop, or clear any stash.

Verify patches against the pinned target, not a remote ref that can move:

```console
$ git range-diff <base>..<tip> <target_oid>..HEAD
```

`=` means unchanged. Read every `` ! `` inner diff: hunk-header/context changes
are benign only when trunk explains them; changed patch lines must match a
reviewed conflict resolution. For an unmatched `<` / `>` pair sharing a
subject, rerun with `--creation-factor=100` before declaring a drop or add.
Confirm each remaining dropped patch already exists on trunk. Stop on an
unexplained content change; keep the recovery refs and user edits intact.

Run the project's defined quality checks once after all conflicts are
resolved. Report failures; fix them in a new commit only when the user asks.
With unresolved replay or saved-edit conflicts, report checks as blocked.
With no defined checks, say so. Never claim checks passed from an earlier run.

## Output

Before sending, check the mode's first-line prefix and section or paragraph
shape. Repair mismatches without narrating the check. Replace first-person
narration with observed changes; do not paraphrase fixed prefixes or headings.

Open with `✓ Rebased N commits onto <remote>/<trunk>` only for a verified
completed replay and restoration. Use `⚠ Rebased ...` for a completed replay
with unresolved saved edits, failed checks, or an unexplained patch change.
Then use exactly these sections:

1. `## Rebase`: replay result, every path from the recorded `overlap`, resolved
   conflicts, and any retained stash SHA. Say when no paths overlap. For
   restored edits, name each path as `git status` shows it (staged,
   unstaged, or both) and say the edits remain uncommitted.
2. `## Content check`: range-diff findings, including each changed patch.
3. `## Checks`: commands and results, or the concrete reason they were blocked.
4. `## Recovery`: original tip and named backup branch; any retained stash
   ref. Undo history only from a clean tree with
   `git reset --keep <backup>`, preserving dirty work first. With an upstream,
   print `git push --force-with-lease --force-if-includes <tracking remote>
   HEAD:<upstream branch>` as a command for the user after review. Derive both
   values from the recorded `upstream`; never push. Without an upstream,
   state that fact and omit publishing advice.

Write impersonally, with plain bullets, no bold labels, and no local paths.
Leave a blank line after each heading. Shell commands go in separate
`console` fences with a `$ ` prompt; split long commands with backslash
continuations, one flag per line. Recovery SHAs are evidence. Omit passed
preflight checks and explanations of the host's tools. End with
`ask-user-choice` options to inspect a changed
patch or finish; without that tool, print `Next: inspect a changed patch, or
done.` With unresolved saved edits, use `Next: resolve <paths>, inspect a
changed patch, or done.` Keep the competing content choices in `## Rebase`,
not an extra paragraph after Recovery.
Report their current state; never say what any choice will leave staged,
unstaged, or committed, before the user has chosen and the restoration has
been verified. Do not suggest
dropping a retained stash.

A stopped reply has exactly three paragraphs: one result sentence, one
state/recovery line, then one decision sentence. No sections, lists, commit
inventory, code snippets, combined-behavior proposals or promises to execute.
Keep the existing choices in prose. Use the `⚠ Stopped:` opening and
`Choose` decision prefix verbatim; substitute observed paths, behavior and
recovery refs into this shape:

```text
⚠ Stopped: src/parser.py has competing tokenization behavior.

The replay is paused with the conflict left in place; backup <backup> retains tip <tip>, and saved edits are <stash or none>.

Choose whether blank input returns an empty list or an empty token.
```

An already-current branch, a fast-forward-only branch, or any preflight
refusal also starts with `⚠ Stopped:`. State that no replay ran and give only
the relevant next choice; do not use a success hero for a no-op. Use
`No replay ran; no recovery refs were created.` as the state line. For an
already-current branch, end with `Next: done.` For a merge-commit refusal,
ask the user to choose a separate merge-handling workflow or leave the branch
unchanged; do not prescribe a bypass command.

Any separately authorized commit follows project conventions and carries no
tool trailer, generated footer, or emoji.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
