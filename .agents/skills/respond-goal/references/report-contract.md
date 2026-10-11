# Report Contract

Contents: Scripts, Reply shape, Hero line, Home-directory halt, Stop rules.

What the `respond-check` skill, the `respond-action` skill, and this skill share about
running scripts and writing replies. Each skill states only what is
specific to it.

## Scripts

A `SKILL.md` reaches the plugin's `scripts/` two levels up, a reference one
level up (`../scripts/`), each from its own directory. Write the resulting
absolute path verbatim in each command; shell variables do not persist
between Bash calls.

The scripts import two shared helpers that sit beside them:
`./ghcli.py` (the `gh` runner) and `./repo_state.py` (git
state). Every skill that loads this file receives both.

## Reply shape

Write the reply as plain text outside any code fence, with plain bullets, no
bold (never `- **Label:** ...`), per `prose-rules.md`. Never name local
absolute paths, temp files, credential file names, or a file and line number
(name the function). Never name the test harness or its stubs, or internal
phase and step names. Write no first person. The example in each skill shows
the shape.

## Hero line

The hero line is the literal first line of the reply. No sentence, label, or
note precedes it, and nothing follows the prescribed parts.

## Home-directory halt

A repository rooted at the home directory, or above it, would sweep
credentials into a stash or a commit. Before any edit, stash, or stage:

```console
$ python3 ./repo_state.py guard
```

Exit 3 halts. The reply is one result sentence and the instruction to run
again from the project's own checkout, with the single option `1. Stop`. It
names no file found there, recaps nothing inspected, and claims no stash,
stage, edit, or commit. the `respond-action` skill opens with
`Stopped before any edit: this repository is rooted at your home directory.`
and this skill with
`Halted before round 1: this repository is rooted at your home directory.`

## Stop rules

No respond skill force-pushes, resolves a review thread, merges, or
approves on a reviewer's behalf. A push happens only under `--push` in
this skill or when the user picks it from a skill's closing panel.
this skill lists its halt conditions under `## Stopping`.
