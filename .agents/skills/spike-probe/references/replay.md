# Replay plan and replay

How this skill, the `spike-bakeoff` skill, and the `spike-ratchet` skill turn a spike
stash into a commit-by-commit plan and, when asked, land it. `<scripts>`
is as defined in `spike-core.md`.

Contents:

- The replay plan
- Replay (only after the plan is approved)

## The replay plan

Produce the commit-by-commit plan. For each planned commit:

- **Subject** in the project's commit format (from Preflight).
- **Contents**: which files/hunks from the spike's changes it takes (the
  delta after a probe on top), and what gets rewritten rather than
  replayed.
- **Decisions to resolve**: each `SPIKE:` marker landing in this commit,
  as a question with a recommendation.
- **Gates**: the per-commit gate commands, right-sized per
  `verification-gates.md`.

Close the plan with the local-vs-CI table and the post-push watch
command: `gh pr checks --watch` for a PR, `gh run watch` when no PR
exists yet, or "none (no remote)".

## Replay (only after the plan is approved)

1. From the original branch, never a scratch branch, apply the spike
   (apply, not pop). The stash stays until the replay finishes green.
   Their own edits are never part of a plan item: after a probe on top,
   pass the user-work SHA so only the spike's delta is applied.

```console
$ <scripts>/spike.sh replay-apply <spike sha> [<user-work sha>]
```

2. Land plan items in order: stage only that item's changes (never a
   `SPIKE:` marker; resolve it per the plan's decision or leave the item
   out), run its gates, commit with the planned message, written per
   `prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailers, and no emoji. A red gate
   stops the replay; report and hand back. Never amend a commit or
   rewrite landed history: a mistake in a landed item gets a follow-up
   item or a hand-back. Prefer file-level splits;
   to split one file, write the relevant hunks to a patch file and
   `git apply --cached <patch>` (`git add -p` is interactive).
   After each commit, read it back with `git log -1 --stat`; the report
   names only commits that printed.
3. After the final item: run any end-of-run `build` bucket, drop the
   spike stash by SHA (it refuses the user-work stash; an `already
   gone` result means nothing to drop), and if the branch has a remote
   counterpart offer to push and watch CI:

```console
$ <scripts>/spike.sh drop <spike sha>
```

4. After a stash-first run, restore their work with
   `<scripts>/spike.sh restore <user-work sha>`. It stays uncommitted. A refused
   restore keeps the stash: report the SHA.
