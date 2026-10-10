# Choosing which repositories are in scope

Run this before any sweep that walks a directory or names more than
the current repository.

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

Default scope is the current repository, which the user chose by
running the command there: it is not fork- or ownership-checked, and
the rules below apply to repositories that `--repo` or `--root` adds.
`--root <dir>` walks a
directory for git repositories, `--repo <path|slug>` names individual
ones, and `--owner <name>` keeps only those whose remote belongs to the
given accounts or organisations.

Run the rules below on every repository a widened scope turns up. Drop
repositories that do not pin the package or tool being moved and those
already at the target. Excluded repositories never come back in through
a flag or a user request: a fork named by `--repo` is reported as a
fork and skipped, with no override. When no repository remains, the
run halts.

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

`./repo_facts.py --fetch <repo>...` fetches the remote, resolves
the default branch (local `HEAD` ref, then `ls-remote`), and prints
`default_branch`, `behind_remote`, `fork_signal`, `linked_worktree` and the
pins read from that branch as one JSON object per repository. It uses the
repository's own remote (`origin`, else the only one); with several remotes
and no `origin` it prints an `error` and the user names the remote. When
`fetch_ok` is false, say in the report that pins may be stale; when
`default_branch` is null, ask the user. A `failed` entry means that fact
could not be read and is unknown, not clean or absent. The script path
resolves from this reference's directory to an absolute path; write it
literally in the command.

## Ask the forge first

`gh` answers the question directly, and its answer beats every
inference below:

```console
$ gh repo view <owner>/<name> --json isFork,viewerPermission
```

**`isFork: true`** — out of scope, whoever owns the fork. Its
dependencies belong upstream. The reply states the fact ("widgets is
a fork of example-org/widgets"), never this reason.

**`viewerPermission: ADMIN` or `MAINTAIN`** — in scope, provided it is
not a fork.

**`viewerPermission: READ` or `TRIAGE`** — out of scope.

**`viewerPermission: WRITE`** — ask. Write access makes you a
contributor, which is not the same as being the person who decides when
this project takes a new version of a dependency.

## When the forge cannot answer

No `gh`, no network, a non-GitHub remote, or no remote at all. Treat a
repository with an `upstream` remote (`fork_signal` true) as a probable
fork: ask, and do not commit. Otherwise fall back to two weaker signals
and require them to agree.

**The owner segment of the remote.** Necessary but not sufficient: an
organisation the user maintains and one they merely contribute to are
indistinguishable by name.

**Authorship of the default branch.** Read the last ten commits on
the default branch found above, not on the working tree's branch:

```console
$ git -C <repo> log \
    --max-count=10 \
    --format='%an <%ae>' \
    <remote>/<default-branch>
```

Compare the commit emails with `git config user.email`, exact address
only. A shared domain (a consumer mail provider, a forge's noreply
domain, an employer with many projects) proves nothing about who
maintains this repository, so a domain match alone is a disagreeing
signal.

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
