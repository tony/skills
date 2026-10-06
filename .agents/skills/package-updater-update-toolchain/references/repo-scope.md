# Choosing which repositories are in scope

Run this before any sweep that walks a directory rather than acting on
one named repository.

A directory of checkouts holds worktrees, forks, vendored clones and
upstream projects read for reference, and every one looks like a git
repository. A commit to someone else's project lands in their history
under the user's name, unasked, and cannot be taken back.

**When ownership is unclear, stop and ask.** A skipped repository costs
one question. A wrong commit costs someone else's review time.

## Contents

- Set the scope
- Skip worktrees
- Find the default branch
- Ask the forge first
- When the forge cannot answer
- What to report

## Set the scope

Default scope is the current repository. `--root <dir>` walks a
directory for git repositories, `--repo <path|slug>` names individual
ones, and `--owner <name>` keeps only those whose remote belongs to the
given accounts or organisations.

Run the rules below on every repository a widened scope turns up. Drop
repositories that do not pin the package or tool being moved and those
already at the target. Excluded repositories never come back in through
a flag or a user request: forks are out of scope, with no override.

## Skip worktrees

A linked worktree shares its history with a canonical clone, so updating
both produces the same commit twice, or a conflict. In a linked worktree
the two directories printed here differ:

```console
$ git -C <repo> rev-parse --path-format=absolute --git-dir --git-common-dir
```

A submodule prints a path here; drop it from scope too:

```console
$ git -C <repo> rev-parse --show-superproject-working-tree
```

Map a worktree back to its clone when you need to, and act on the clone
named by `--git-common-dir`.

A directory sweep also picks up several clones of one repository under
different names. Deduplicate by remote URL and keep one.

## Find the default branch

Fetch first, so the comparison is not against stale refs. When the fetch
fails, say in the report that pins may be stale:

```console
$ git -C <repo> fetch origin
```

Read the default branch from the local ref:

```console
$ git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD
```

That ref is unset in some clones and the command exits non-zero. Ask the
remote instead; if that fails too, ask the user:

```console
$ git -C <repo> ls-remote --symref origin HEAD
```

## Ask the forge first

`gh` answers the question directly, and its answer beats every
inference below:

```console
$ gh repo view <owner>/<name> --json isFork,viewerPermission
```

**`isFork: true`** — out of scope, whoever owns the fork. Its
dependencies belong upstream.

**`viewerPermission: ADMIN` or `MAINTAIN`** — in scope, provided it is
not a fork.

**`viewerPermission: READ` or `TRIAGE`** — out of scope.

**`viewerPermission: WRITE`** — ask. Write access makes you a
contributor, which is not the same as being the person who decides when
this project takes a new version of a dependency.

## When the forge cannot answer

No `gh`, no network, a non-GitHub remote, or no remote at all. Fall back
to two weaker signals and require them to agree.

**The owner segment of the remote.** Necessary but not sufficient: an
organisation the user maintains and one they merely contribute to are
indistinguishable by name.

**Authorship of the default branch.** Read the last ten commits on
the default branch found above, not on the working tree's branch:

```console
$ git -C <repo> log \
    --max-count=10 \
    --format='%an <%ae>' \
    origin/<default-branch>
```

Match on the email domain rather than one exact address — the same
person commits as more than one identity, and a project run under an
organisation's own address is still theirs.

Agreeing signals decide it, but a repository settled this way is
committed locally and not pushed unless the user approves the push in the
plan. **Disagreeing signals mean ask**, and so
does either of these on its own:

- Trunk's recent commits are entirely from bots or coding agents, which
  says nothing about who owns the repository.
- The remote's owner is an organisation and nothing else corroborates
  maintainership.

## What to report

Say which repositories were excluded and under which rule: fork,
permission, worktree, duplicate clone. A sweep that silently drops
repositories reads as one that found them all current.

List the ones you stopped to ask about separately from the ones you
excluded outright. Those are a decision waiting on the user, not a
finding.
