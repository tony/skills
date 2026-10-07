---
name: tighten
description: "Use when tightening named files or pasted text in place by removing verbose prose, brittle references, and low-value noise."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[paths/globs] [--stdin] [--gates] [--diff-only]"
user-invocable: true
disable-model-invocation: true
---


# `/lean:tighten`

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

If `$ARGUMENTS` is empty, ask which files via `AskUserQuestion`. Without
an interactive question tool (Codex, headless runs), print the usage
and stop. A request that says "go ahead" authorizes the edits it
names, never a commit.

## Steps

1. **Resolve targets.** Expand paths/globs, or read stdin with
   `--stdin`. Reject an empty target set with a clear message; with `--stdin` and
   no text, print the usage and stop.
2. **Load the rules and voice.** Read
   `../../references/prose-rules.md` and
   `../../references/lean-rubric.md`, then `./AGENTS.md` and
   `./CLAUDE.md` for the host's rubric and accepted voice. For
   `--gates`, take the format/lint/typecheck commands from a checks
   section in those files; if none is defined, skip gates.
3. **Detect.** Flag what the prose rules list as cut. Preserve every
   load-bearing reference and "why" comment.
4. **Preview and confirm.** Show the proposed edits and confirm via
   `AskUserQuestion` before writing; the preview and the printed diff
   (Step 6) are the review surface. Skip when `--diff-only` or
   `--stdin`. Without an interactive question tool, act as
   `--diff-only`.
5. **Apply in place.** Use `Edit`. Replacements are concrete and
   shorter than the original.
6. **Diff.** Print `git diff -- <targets>`. Skip for `--diff-only` and runs
   without a question tool (nothing was edited); for `--stdin`, print the tightened text as the whole reply. With `--gates`, run the
   discovered checks once and report; commit on neither pass nor fail.
7. **Report and hand off.** Write it per
   `../../references/prose-rules.md`: a one-line count of findings
   resolved and skipped, with no section labels and no recap of what
   changed. Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

   ```text
   5 findings resolved, 1 skipped.
   ```

   With `--diff-only` or no question tool the hero is
   `6 findings proposed, 0 applied.` A stopped run is one result
   sentence, then what the user needs to do.

   Then offer next steps via `AskUserQuestion`: commit, or
   discard the edits. Without a question tool, print the options as a
   plain list and stop. Review the printed diff first, since
   `git checkout -- <file>` resets the whole file to HEAD and drops any
   other uncommitted work in it. A commit message carries no
   `Co-Authored-By`, no "Generated with" or other tool trailer, and no
   emoji. For `--stdin`, skip the handoff: the reply is the tightened
   text with no lead-in, then at most one line, and only to name
   load-bearing text kept that the user might expect cut. Never narrate
   what was removed.

## What this does not do

- Delete whole files. Report them instead.
