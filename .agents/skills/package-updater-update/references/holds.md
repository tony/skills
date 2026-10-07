# Holding a package back

A hold is a decision to stay behind on purpose. The next person to run
the updater will see a package that looks stale and try to fix it, so a
hold needs more explanation than any version bump.

Every hold has a **condition that ends it**. Record it when you add the
hold, and release the hold when it is met. A hold with no condition is
indistinguishable from neglect.

## Contents

- Where holds live
- The reason cannot live in the file
- Commit grammar
- What earns a hold
- Auditing holds
- Cooldown is not a hold

## Where holds live

npm-check-updates reads an `.ncurc` config file in one of several
formats; `ncu --help` and its documentation list the names and the
`reject` option's accepted forms (exact names, and patterns for holding
a family together). The `reject` array names packages `ncu` must not
offer.

**Do not assume a `"ncu"` key in `package.json` is read.** Confirm any
hold works: run `ncu` after writing it and check the package is no
longer offered.

**Config can sit beside each package file, not only at the repository
root.** Check the documentation for the installed `ncu`. A workspace can
then hold a package in one member and not another, for example two
members that need a preview build while the rest of the tree tracks
releases, and a root-only scan under-reports holds. Enumerate every
config in the tree:

```console
$ find . -name '.ncurc*' -type f
```

Releasing the last hold ends one of two ways: `{"reject": []}` left in
place so the next hold has somewhere to go, or the file deleted outright.
Follow whichever the repository already does, and do not "tidy" an empty
`reject` array away, since the next reader sees a difference that `ncu`
does not.

## The reason cannot live in the file

A JSON config cannot carry comments, and `ncu` may reject keys it does
not know, so a `$comment` entry can break the tool instead of documenting
the hold. Run `ncu` after any edit to the file and confirm it still
loads.

The commit message is the only durable record of why a package is held.
If a hold needs an inline explanation, use a config format that supports
comments rather than inventing a key.

## Commit grammar

Scope by the file, and name the condition in the subject.

Adding a hold:

```text
.ncurc: Ignore `@biomejs/biome` 2.3.5 -> 2.3.6 until they fix class methods
```

Releasing one, naming what fixed it:

```text
.ncurc: Unignore `@biomejs/biome` (2.3.7 fixed issue)
```

## What earns a hold

Each shares one shape: a condition outside the repository that has not
happened yet.

- **Upstream bug** — the release is broken for a use this project makes.
  Released when the fixing version ships.
- **Ecosystem catch-up** — a major that a framework this project depends
  on does not support yet.
- **Runtime floor** — a release that drops a runtime this project still
  supports. Released when the project drops it too.
- **Migration not yet done** — a major whose upgrade is real work,
  deliberately deferred.
- **Maintainer broke the package** — a release that changed something
  fundamental in a way that is not going to be reverted.

A hold is not a way to skip release notes: "this looked risky" is a
reason to read them.

## Auditing holds

Every sweep checks the existing holds, not just the outdated packages.
For each entry in every `reject` array, report:

- The condition recorded in the commit that added it, and whether that
  condition is now met — a hold whose fixing version has shipped should
  be released in this run.
- Holds with no recoverable reason. Do not silently release these; a
  reason that was never written down might still be real. Surface them
  and let the user decide.
- Holds duplicated unevenly across workspace members, where one package
  rejects something its siblings do not. That is usually drift rather
  than intent.

A fleet-wide hold is added and released across every repository that
carries it. Both directions fan out, and both are easy to half-finish:
re-enumerate the configs after the pass.

## Cooldown is not a hold

An ecosystem cooldown gates every package by release age. A hold names
one package and one condition. Never use a `reject` entry to wait out a
cooldown: it outlives the window.
