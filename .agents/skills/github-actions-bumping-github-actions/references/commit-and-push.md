# Committing and publishing bumps

## Contents

- Edit exactly the approved lines
- Commit message
- Commit
- Reuse a branch
- Push
- Read back what was published

## Edit exactly the approved lines

Replace each pin line the inventory recorded, old text to new text, in the
checkout the commit is made in (its worktree path when it uses one). When
the old text is not found, the file changed after the inventory: stop for
that repository and inventory it again. Do not edit by line number.

## Commit message

The subject and body follow the project's own conventions from its AGENTS.md
or CLAUDE.md. The body says what changed upstream, what it means for this
repository, and links every major release in the span. Write the commit
message, and any pull-request title and body, per `prose-rules.md`. No
`Co-Authored-By`, no "Generated with" or other tool trailer, no emoji, and
no mention of that rule in the reply. Never cite a dependabot pull request
(`dependabot-closeout.md` holds that rule).

## Commit

Stage the named workflow files with `git -C <path> add -- '<file>'...`; never
`add -A`, `add .`, or `commit -a`. Then read what is staged:

```console
$ git -C <path> diff \
    --cached \
    -U0
```

Commit only when every changed line is a `uses` pin or its version comment
and each matches an approved plan entry. Anything else, such as a
concurrent edit, stops that repository: name the file and leave the work
in place.

Run hooks; never pass `--no-verify`. A hook that fails stops that
repository and its output is reported. After the commit, show the commit:

```console
$ git -C <path> show \
    --format=%h \
    -U0 \
    <sha>
```

It must show the approved lines and nothing else. A hook that rewrote
other content makes the commit unexpected: report it and do not push.

## Reuse a branch

```console
$ python3 <absolute-path>/fleet.py branch \
    --subject '<approved subject>' \
    '<path>' \
    '<remote>/<default>' \
    '<branch>'
```

prints the branch to commit on: `<branch>` when it is free, the same name
when an earlier run left it holding only commits with an approved
`--subject` (repeat the flag per plan entry) and no other worktree has it
checked out, otherwise `<branch>-2`, `<branch>-3`. Use the printed name; its
`reuse` field says whether it exists. Never reset, rebase, or force an
existing branch.

## Push

Push only with `--push`, an explicit request to push, or `--pr`, which
pushes its own branch and nothing else. With `--push` and no `--pr`, push
`HEAD` to the default branch: `git -C <path> push <remote> HEAD:<default>`
from the worktree. A bare `--push` in a headless run is an explicit request.
Before pushing, check what the push would publish:

```console
$ python3 <absolute-path>/fleet.py pushable \
    --made '<sha>' \
    '<path>' \
    '<remote>/<default>'
```

Repeat `--made` for every commit SHA recorded this run, and add `--subject`
for each approved plan entry when resuming. Exit 0 means every commit that
would be published qualifies. Exit 1 prints the commits that do not: they are
the user's, so do not push, name them and how the branch diverges, never
advise a reset or drop of them, and print the push command. Stop a fleet
loop on a rate-limit error or a rejected push and report which repositories
remain. A rejected push is not retried with force. A local default branch
holding the user's commits has diverged from the remote after a push from a
worktree; report it as diverged, not behind.

## Read back what was published

After a push, ask the remote for the target:

```console
$ git -C <path> ls-remote \
    <remote> \
    refs/heads/<target>
```

Report "pushed" only when it prints the SHA just pushed. A different or
empty answer is reported as unconfirmed, with the SHA the remote returned.
Without a push, report the local branch holding the commit and print its
push command.

After opening a pull request with `--pr`, read it back from the number in the
URL `gh pr create` printed:

```console
$ python3 <absolute-path>/pins.py pr-state <slug> <n> open
```

Report the pull request only when it exits 0; the URL it prints is the one to
list.
