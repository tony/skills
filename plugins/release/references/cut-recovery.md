# Cut stop and recovery reference

What `/release:cut` reports when a run stops after it has changed something,
and the recovery it offers. The reply opens with `Stopped:`, is one result
sentence, then bullets with what the user does. Write it per
`prose-rules.md`, as plain text outside any code fence, with plain bullets, no
bold and no local paths.

## State to report

- Distinguish staged, working and untracked changes, and any change to HEAD
  or refs. Claim a state unchanged only after comparing the recorded states
  to the observed ones, and never say the whole repository is untouched.
- Name the failed gate or command, its exit status and the local commit id
  when one exists. No gate logs.
- Mark unavailable evidence unverified: unreadable state, a readback that did
  not run.
- Report tag and push outcomes that were observed. After a failed or
  unverified push, name the refs the readback confirmed and mark the rest
  unverified.
- Use one command per bullet.

## Recovery after a gate or commit failure

Recovery means reviewing the surviving changes, repairing the failure without
weakening gates, hooks or signing, rerunning every original required gate,
rechecking HEAD, refs, index and working files, then staging only approved
release changes and retrying the commit. A prior green result does not cover
repairs or hook edits. If state is unreadable or changed unexpectedly,
preserve it and stop for review. After a successful retry, repeat the
Phase 5 verification and follow Phase 6 under the original flags.

Offer recovery or a reviewed start-over. `cut` refuses a dirty tree, and a
start-over choice does not authorize discarding unrelated changes in the same
files: preserve current work, review the exact edits before selecting an
undo, and never print a blanket whole-path restore recipe.

## Examples

A signing failure with unchanged HEAD and refs, release edits still staged,
and no tag or push:

```text
Stopped: the release commit failed (signing error); HEAD and refs are unchanged, release edits remain staged, no tag was created and nothing was pushed.

- Review surviving changes and fix signing without disabling it or the hooks.
- Re-run all original quality gates, recheck repository state, stage only approved release changes and retry the commit with the subject "Tag v0.4.0".
- After a successful commit and the Phase 6 checks, run only the tag and push steps authorized by the original flags.
```

A gate that left both staged and working edits with unchanged HEAD and refs:

```text
Stopped: the test suite failed; HEAD and refs are unchanged, and release edits remain staged and unstaged.

- To resume: review surviving changes, fix the failure without weakening gates, hooks or signing, re-run all original quality gates, recheck repository state, and stage only approved release changes before retrying the release commit.
- To start over: preserve current work and select the exact release edits to undo without discarding independent changes in the same files.
- Re-run /release:cut 0.4.0 --tag only after the reviewed undo leaves a clean tree.
```

A rejected branch push, with the readback marking the rest unverified:

```text
Stopped: the branch push was rejected (not a fast-forward); release commit 4e1a9b2 and tag v0.4.0 exist locally, the remote branch is unchanged and the tag was not pushed.

- Review the remote branch and decide how to integrate its changes; this skill never moves or deletes a tag.
- Publish the commit and tag yourself once the release commit is final.
```

An unapproved empty section after a verified fast-forward with no release
edits. If edits or a failed command already occurred, report that partial
state instead, and preserve it without automatic rollback:

```text
Stopped: the Unreleased section has no entries; synchronization updated the checkout, and no release edits were made.

- To release anyway, re-run the same command and explicitly approve an empty 0.4.0 release for this repository.
- Otherwise add the notes under the Unreleased heading and commit them, then re-run.
```
