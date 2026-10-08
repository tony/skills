---
name: lean-tighten
description: >-
  Use when tightening named files or pasted text in place by removing
  verbose prose, brittle references, and low-value noise.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[paths/globs] [--stdin] [--gates] [--diff-only]"
  source: "plugins/lean/skills/tighten/SKILL.md"
---

# this skill

Tighten specified files in the working tree and print a diff. Never
commits, never pushes, never requires a clean tree, never scans
repo-wide.

## `$ARGUMENTS`

- `paths/globs` — files to tighten (via `git ls-files -- <glob>` when
  tracked, else literal paths).
- `--stdin` — tighten a pasted draft read from stdin instead of files;
  print the tightened text and edit nothing.
- `--gates` — after editing, run the project's discovered
  format/lint/typecheck once and report. Never commits.
- `--diff-only` — show what would change without editing.

If `$ARGUMENTS` is empty, ask which files via `ask-user-choice`; without
an interactive question tool (Codex, headless runs), print the usage
and stop.

With targets but no question tool, act as `--diff-only` unless the
request itself says "go ahead": that authorizes the edits it names,
never a commit.

## Steps

1. **Resolve targets.** Expand paths/globs, or read stdin with
   `--stdin`. Reject an empty target set with a clear message; with `--stdin` and
   no text, print the usage and stop.
2. **Load the rules and voice.** Read
   `references/prose-rules.md` and
   `references/lean-rubric.md`, then `./AGENTS.md` and
   `./CLAUDE.md` for the host's rubric and accepted voice. For
   `--gates`, take the format/lint/typecheck commands from a checks
   section in those files; if none is defined, skip gates.
3. **Detect.** Flag what the prose rules list as cut. Preserve every
   load-bearing reference and "why" comment.
4. **Preview and confirm.** Show the proposed edits and confirm via
   `ask-user-choice` before writing; the preview and the printed diff
   (Step 6) are the review surface. Skip when `--diff-only` or
   `--stdin`; a `--diff-only` run prints its proposal in step 6. Without an interactive question tool, follow the
   headless rule in `$ARGUMENTS`.
5. **Apply in place.** Use `Edit`. Replacements are concrete and
   shorter than the original.
6. **Diff.** Print `git diff -- <targets>`; for an untracked target print
   `git diff --no-index -- /dev/null <file>` instead. A `--diff-only` run
   prints the proposed edits as a unified `diff` block instead (the
   proposal, not `git diff`). Skip for runs that edited nothing; for
   `--stdin`, print the tightened text as the whole reply. With `--gates`, run the
   discovered checks once and report; never commit, whatever the gates report.
7. **Report and hand off.** Write it per
   `references/prose-rules.md`: a one-line count of findings
   (one per edited span) resolved and skipped, with no section labels and no recap of what
   changed. Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

   ```text
   5 findings resolved, 1 skipped.
   ```

   With `--diff-only`, or no question tool and no go-ahead, the hero is
   `6 findings proposed, 0 applied.`, followed by the proposed edits in
   a `diff` block and nothing else:

   ````text
   2 findings proposed, 0 applied.

   ```diff
   --- a/NOTES.md
   +++ b/NOTES.md
   @@ -3 +3 @@
   -We should probably consider maybe running the sync job nightly.
   +Run the sync job nightly.
   ```
   ````

   A rewrite adds no fact the original lacks. A stopped run is one result
   sentence, then what the user needs to do. The reply adds no sentence
   outside the shape, anywhere (not even to say nothing was edited, why,
   or what the session cannot do); do not explain text you kept.

   After a proposal-only run (nothing written), offer to apply the proposal
   or stop; there is nothing to commit or discard. Otherwise offer next
   steps via `ask-user-choice`: commit, or discard the edits. Without a question tool, print the options as a
   plain list and stop. Offer a file option only for files on disk; pasted
   text has none and is never matched to a scaffold file. Review the
   printed diff first, since `git checkout -- <file>` resets a tracked
   file to HEAD and drops any other uncommitted work in it; to discard
   edits to an untracked file, restore the original text you read before
   editing, or delete the file when it was untracked before the run and the user says it is new. A commit message carries no
   `Co-Authored-By`, no "Generated with" or other tool trailer, and no
   emoji. For `--stdin`, skip the handoff: the reply is the tightened
   text with no lead-in, then at most one line, and only to name
   load-bearing text kept that the user might expect cut. Never narrate
   what was removed.

## What this does not do

- Delete whole files. Report them instead.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
