# Spike core

The steps every spike skill shares: preflight, setup, the probe loop, the
exit gate, and the stash. the `spike-probe` skill, the `spike-bakeoff` skill, and
this skill read this file instead of each other.

## Contents

- Scripts
- Preflight
- Setup
- The probe loop
- Exit gate
- Stash
- Worktree root

## Scripts

`./spike.sh` holds the git plumbing. The shell's working directory
is the project, not this file, so resolve `../scripts` against this file's
directory to an absolute path and write that path literally in every command
below, where `<scripts>` stands. The script exits 1 with a one-line reason
when it refuses, 2 on a usage error.

## Preflight

Before writing any code:

1. Confirm a git repository with at least one commit, and that its root
   does not contain the home directory. A dotfile repository rooted at
   home would have `git add -A` and `git reset --hard` sweep the whole
   home directory, credentials included:

```console
$ <scripts>/spike.sh guard
```

   Any output but `ok` halts before touching anything. Say what is
   missing in plain words, not the command that found it: no commits (the
   user makes the initial commit, since a spike never commits), a
   repository rooted at their home directory (the user opens the project's
   own repository), or an unset or invalid `HOME` (the user fixes it).
2. Read the project's `AGENTS.md` / `CLAUDE.md` /
   `.github/CONTRIBUTING.md` for quality checks, commit format, and test
   conventions, then resolve the five gate buckets (`format`, `lint`,
   `typecheck`, `test`, `build`) and the CI-coverage split with the gate
   reference the skill links.
3. Run `git status --porcelain`. A dirty tree halts here: ask whether to
   stash their work first, probe on top of it, or abort. Non-interactive
   default: abort. Record the choice; nothing is saved or switched until
   the brief is approved. Either way their work is saved as a stash named
   `user work before spike`, and the printed SHA is the **user-work
   SHA**: record it, report it with its restore command in every run, and
   never drop it. Skills that run without "probe on top" offer only stash
   first or abort.
4. With `--branch`, check that the name is free
   (`git rev-parse --verify --quiet refs/heads/<name>` prints nothing);
   a name that exists halts: ask for another.
5. Locate the code the goal touches (existing modules, tests,
   fixtures), enough to work in the project's idiom.

## Setup

Once the brief is approved and before the first edit:

1. A dirty tree answered *stash first*: the tree is cleaned:

```console
$ <scripts>/spike.sh save-user
```

   The restore waits for the exit path to finish, and is the skill's to
   place: the `spike-probe` skill restores after its stash, the `spike-bakeoff` skill after
   its last contender is stashed, this skill only after its exit,
   never between rounds.
2. A dirty tree answered *probe on top*: the stash is saved but their
   files stay in the tree, so the spike builds on them. Staged edits come
   back unstaged and untracked files stay untracked; contents are
   unchanged:

```console
$ <scripts>/spike.sh hold-user
```

3. With `--branch`, create the scratch branch. The command prints the
   original branch (a SHA when HEAD is detached); use that literal value
   when leaving it:

```console
$ <scripts>/spike.sh branch-start <name>
```

## The probe loop

Code the shortest path to "proven". During this phase:

- Verify with the **cheapest signal that moves you forward**: the one
  test file or smoke command that exercises the new code, not the full
  suite or the build.
- Mark shortcuts as you take them with a `SPIKE:` comment (hardcoded
  values, skipped edge cases, undecided semantics). They become plan
  items, not debt to fix during the probe.
- Stay inside the goal. Adjacent problems go in the plan's "observed,
  not addressed" list.
- Record **stumbling blocks**: places the approach itself fought back
  (an API that will not compose, a constraint that surfaced too late).
  Unlike a `SPIKE:` marker (a shortcut you chose) or an adjacent
  problem, a stumbling block is evidence the *approach* may be wrong:
  the reason to reach for the `spike-bakeoff` skill.

## Exit gate

Once proven, run the fast local buckets exactly as discovered:
`format`, `lint`, `typecheck`, and the scoped `test` command. Run
`build` only if the change plausibly affects build output; otherwise
note it as CI-deferred.

Gate failures here are information, not work: fix formatting, and
record the rest as plan items.

Run gates as discovered, including mutating ones (`--fix` linters,
formatters). If a gate changes any file, re-run the proving check once:
the stash must hold code proven *after* its last modification.

## Stash

Stash everything, untracked files included, with a recovery ref. Stash one
at a time: the script holds a lock and refuses a second stash that starts
before the first ends. Never read `stash@{0}`: on an unchanged tree
`git stash push` exits 0 and `stash@{0}` is another stash's entry. The
script prints the stash's own SHA instead.

1. List what no ignore rule covers. Files matched by `.gitignore` are never
   stashed, and the script already leaves Python bytecode in place. Pass
   `--leave <path>` on the stash command for each remaining path that is
   build output, logs, or a cache rather than source, so it neither
   travels with the spike nor lands in a replay:

```console
$ <scripts>/spike.sh untracked
```

2. Create a message file and print its path. The message is
   `spike: <goal> (<what passed, what's undecided>)`; the goal can come
   from a pasted trace, so it never goes inside a shell string. Write the
   message to the printed path with the file-writing tool, then pass the
   path:

```console
$ mktemp "${TMPDIR:-/tmp}/spike-message.XXXXXX"
```

```console
$ <scripts>/spike.sh stash -F <message path>
```

   After a probe on top, pass the user-work SHA so their files go back
   into the tree and the stash records the spike:

```console
$ <scripts>/spike.sh stash-on-top <user-work sha> -F <message path>
```

   Delete the message file (`rm -f <message path>`) once the stash printed.
3. Record the printed SHA in the report; `git stash apply <sha>`
   restores it. The output `no changes` means record "no changes", not a
   SHA. A refused restore after `stash-on-top` still printed the spike
   SHA first: report both SHAs. Run this on every SHA before reporting
   it; it prints the SHA back when real:

```console
$ git rev-parse --verify <sha>^{commit}
```

   After a probe on top the stash holds their work plus the spike, so
   build the plan and the replay from the spike's own delta, never the whole stash:

```console
$ <scripts>/spike.sh delta <user-work sha> <spike sha>
```

   With `--keep-tree` after a probe on top there is no spike SHA: the
   tree holds their edits and the spike together, so build the plan from
   the tree's diff against the user-work SHA:

```console
$ <scripts>/spike.sh delta <user-work sha>
```

4. After a stash-first run that is not replaying, put their work back and
   confirm the tree matches its pre-spike state with `git status`. A
   refused restore changes nothing and keeps the stash: report the SHA
   and stop, and never drop it.

```console
$ <scripts>/spike.sh restore <user-work sha>
```

5. With `--branch`, return to the original branch and delete the
   scratch branch (it holds no commits, so `-d` succeeds). Uncommitted work
   follows you. With `--keep-tree`, stay on the scratch branch and give
   the user the return command instead.

```console
$ <scripts>/spike.sh branch-end <orig> <name>
```

## Worktree root

the `spike-bakeoff` skill and every this skill round that bakes off needs a root
for its contender worktrees. Create it once, outside the repository, print
it, and use the printed path literally afterwards; a ratchet reuses the
same root across rounds. Name each contender `<n>-<slug>`: that is its
directory and its stash message prefix. Worktrees are detached, so no
contender has a branch.

```console
$ mktemp -d "${TMPDIR:-/tmp}/bakeoff.XXXXXX"
```
