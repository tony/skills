---
name: lean-tighten
description: >-
  Use when tightening named files or pasted text in place by removing
  verbose prose, brittle references, and low-value noise.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
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

If `$ARGUMENTS` is empty, ask which files via `ask-user-choice`. Without
an interactive question tool (Codex, headless runs), print the usage
and stop. A request that says "go ahead" authorizes the edits it
names, never a commit.

## Steps

1. **Resolve targets.** Expand paths/globs, or read stdin with
   `--stdin`. Reject an empty target set with a clear message; with `--stdin`, ask
   for the text.
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
   `--stdin`. Without an interactive question tool, act as
   `--diff-only`.
5. **Apply in place.** Use `Edit`. Replacements are concrete and
   shorter than the original.
6. **Diff.** Print `git diff -- <targets>`. Skip for `--stdin`, which instead
   prints the tightened text as the whole reply. With `--gates`, run the
   discovered checks once and report; commit on neither pass nor fail.
7. **Report and hand off.** Write it per
   `references/prose-rules.md`: a one-line count of findings
   resolved and skipped, with no section labels and no recap of what
   changed. Then offer next steps via `ask-user-choice`: commit, or
   discard the edits. Review the printed diff first, since
   `git checkout -- <file>` resets the whole file to HEAD and drops any
   other uncommitted work in it. A commit message carries no
   `Co-Authored-By`, no "Generated with" or other tool trailer, and no
   emoji. Skip this step for `--stdin`; after the tightened text, add
   one line only for load-bearing text kept that the user might expect
   cut.

## What this does not do

- Delete whole files. Report them instead.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
