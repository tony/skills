# this skill edge cases

| Case | Behavior |
|---|---|
| Merge commits in range, no `--apply-rebase` | Permitted; patches and fixups work, and the user can rebase later with `--rebase-merges`. |
| Root commit in range | Warn; rewriting it needs `git rebase --root`. |
| Empty diff after an edit | Skip the fixup and record a no-op. |
| Single-commit branch, no body | A reword commit autosquashes cleanly. |
| `--message-only` and diff slop exists | Report the skipped diff findings; build reword commits only. |
| Linked worktrees | Permitted; run directories resolve through `git rev-parse --path-format=absolute --git-path`. |
| Existing `fixup!` or `amend!` commits on the branch | Detect with `git log --format=%s` and keep subjects starting `fixup! ` or `amend! `; offer to autosquash them first. |
| Non-UTF-8 commit message | Skip message checks for it; warn. |
| Pre-commit hook changes staged content during a fixup | `apply.sh` aborts that step with the hook's stderr; the user fixes it and re-runs. The skill never uses `--no-verify`. |
| `.gitignore` covers a file a patch modifies | `git add` fails; `apply.sh` aborts that step. |
| Git older than 2.32 | See Step 7. |
| Override file is git-tracked and dirty | Warned at Step 5 (see Registry load). |
| Registry edited between materialize and apply | `apply.sh` exits 1. |
