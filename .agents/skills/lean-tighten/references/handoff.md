# Handoff rules

The shared reference for `lean-writing`, this skill, and
the `lean-trim-comments` skill.

## Commit messages

A commit message carries no `Co-Authored-By`, no "Generated with" or
other tool trailer, and no emoji.

## Discarding edits

Review the printed diff first. `git checkout -- <file>` resets a tracked
file to HEAD and drops any other uncommitted work in it. To discard
edits to an untracked file, restore the original text read before
editing, or delete the file when it was untracked before the run and the
user says it is new.

## Next steps

Offer them through `ask-user-choice`. When no question tool is
available, print the same options as a plain list under the label
`Next steps:` and stop.
