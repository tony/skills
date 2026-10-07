# Ecosystem discovery and apply

Read before running anything that resolves a version.

## Contents

- Python with uv
- Python with poetry or pip
- Node with pnpm
- Node with npm or yarn
- Rust
- Go
- When a project has no established procedure
- Runtime and toolchain pins
- Supply-chain cooldown
- Release publication time

Detect an ecosystem by the files present, never by the project's name or
language tag. A repository can carry several (a Python package with a docs
site has both `uv.lock` and `pnpm-lock.yaml`); each updates on its own
track with its own commit.

Run the project's own wrapper when it has one: a `justfile`, `Makefile`,
or `package.json` script named for the update is the maintained path.

## Python with uv

Marked by `uv.lock` beside `pyproject.toml`.

Discovery and apply are usually one step: the lockfile diff is the
report. Use a separate discovery pass to decide before writing:

```console
$ uv lock --upgrade --dry-run
```

```console
$ uv tree --outdated --depth 1
```

**Apply** the bulk refresh:

```console
$ uv sync --all-extras --dev --upgrade
```

**Apply** to one package, leaving everything else pinned:

```console
$ uv lock --upgrade-package <name>
```

`uv.lock` is the only artifact the bulk refresh commits. Confirm the lock
moved: a floor raised in `pyproject.toml` does nothing until the resolver
rewrites the lock.

## Python with poetry or pip

Marked by `poetry.lock`, or by `requirements*.txt` with no lock at all.

Poetry discovers with `poetry show --outdated` and applies with
`poetry update`. A bare requirements file has no resolver of its own;
find outdated pins with `uv pip list --outdated` against the active
environment and edit the file directly.

## Node with pnpm

Marked by `pnpm-lock.yaml`.

**Discover** with `ncu`, which reads manifests rather than the installed
tree. Run it bare to report without writing:

```console
$ ncu
```

`pnpm outdated` reads the installed tree instead and reports a different
set; prefer `ncu` so discovery and apply agree on what "outdated" means.

**Apply** the in-range manifest bump, then install. `--target minor`
keeps every major out of the bulk refresh (`ncu --help` documents
`--target`); `ncu` takes majors by default. A major is
a named bump with its own commit, applied with `ncu -u --target latest
<name>`:

```console
$ ncu -u --target minor
```

```console
$ pnpm install
```

`ncu` acts on the manifest in the current directory. Confirm the
workspace options with `ncu --help`, or recurse to the members:

```console
$ pnpm --recursive exec ncu -u --target minor
```

**Apply** an in-range refresh, which moves transitives without touching
any manifest:

```console
$ pnpm update
```

`ncu -u --target minor` edits `package.json` and lands as a dependency bump; `pnpm
update` edits only the lockfile and lands as an in-range transitive
refresh. They are separate commits.

### Clean reinstall

Destructive, and not part of the routine apply: use it only when an
install fails or leaves a stale tree. Put it in the plan, name the
directories it deletes, and run it only after the user confirms.

Derive the directories from the manager's own workspace config, never
from a layout assumed by name. This lists the root and every member:

```console
$ pnpm ls --recursive --depth -1 --parseable
```

Delete `node_modules` under exactly the directories that command lists,
the user-confirmed set, then run `pnpm install`.

### What ncu cannot see

**Catalog entries.** A version pinned in `pnpm-workspace.yaml` under
`catalog:` is in no `package.json`, so `ncu` never reports it. Check the
catalog by hand on every sweep.

**Overrides and resolutions.** Same problem, same fix.

### Holding a package back

`.ncurc` carries a `reject` array of packages `ncu` must not offer. It
resolves next to the package file, so a workspace member can hold a
package its siblings track — a root-only scan under-reports holds.

Adding and releasing a hold are both commits, and both name the
condition; the commit message carries the reason.

For a one-off exclusion that is not worth checking in, `ncu -u -x <name>`.

## Node with npm or yarn

`npm outdated` and `npm update`; `yarn outdated` and `yarn up`. The
lockfile is `package-lock.json` or `yarn.lock`. Everything else in the
pnpm section applies unchanged, except the cooldown key.

## Rust

Marked by `Cargo.lock`.

Discover with the resolver:

```console
$ cargo update --dry-run
```

`cargo update` applies an in-range refresh, touching only the lockfile.
Raising a version in `Cargo.toml` is a manifest edit and a separate
commit; `cargo upgrade` does it but ships in `cargo-edit`, so confirm
the subcommand exists before putting it in a plan.

## Go

Marked by `go.mod`. `go list -m -u all` reports available upgrades;
`go get -u ./...` followed by `go mod tidy` applies them. Both `go.mod`
and `go.sum` are committed together.

## When a project has no established procedure

The Poetry, pip and Go commands above come from the tools' own
documentation, not from a procedure the project settled on. Say so in the
plan and let the user confirm the command before its first run there.

## Runtime and toolchain pins

Marked by `.tool-versions`, `.nvmrc`, `.python-version`, or a
`mise.toml`. These pin the tools that resolve everything above, so they
move first and on their own, one tool per commit.

Discover with the version manager that reads the file:

```console
$ mise outdated
```

For a tool with no manager entry, ask the vendor's own release feed
rather than memory, and confirm the version exists before writing it.

`packageManager` and `engines` in `package.json` are toolchain pins too,
despite living in a manifest. They never ride along with a dependency
bump.

## Supply-chain cooldown

A cooldown makes the resolver ignore releases younger than a threshold.
Each ecosystem configures it with its own key, unit, and strictness, and
those change between releases. Read them from the installed tool, and do
not copy a key or unit from another repository's config.

Find the setting, then read its documentation:

```console
$ uv lock --help
```

```console
$ pnpm --help
```

```console
$ npm help config
```

```console
$ ncu --help
```

Search the output and the vendor's settings page for `exclude-newer`
(uv), `minimumReleaseAge` (pnpm), `min-release-age` (npm), and
`cooldown` (ncu); these are search hints, not keys to copy. A tool that lists none has no cooldown support in the
installed version. Settings pages:
[uv](https://docs.astral.sh/uv/reference/settings/),
[pnpm](https://pnpm.io/settings),
[npm](https://docs.npmjs.com/cli/using-npm/config).

Before computing a lapse time, confirm from those sources the unit
(minutes, days, or a duration string), whether a too-young pinned range
fails the install or falls back, and whether the lockfile records the
window. Read what the tool prints on a run to confirm the window is in
effect, and do not report versions it gates as current.

Check for a cooldown before reporting a package as current: a release
inside the window is invisible to the resolver, so a gated tree looks up
to date.

## Release publication time

The cooldown check compares a release's publication time with the
window. Read the time from the registry in this run; an empty result or
a non-zero exit means the version is not published, so stop. Each
command prints one timestamp (PyPI's is the earliest file upload).

PyPI, for a Python package or a tool published there (uv):

```console
$ curl -fsS https://pypi.org/pypi/<name>/<version>/json | jq -r '[.urls[].upload_time_iso_8601] | min'
```

npm, for any Node package:

```console
$ npm view <name> time --json | jq -r '.["<version>"]'
```

crates.io, which rejects a request with no user agent:

```console
$ curl -fsS -A 'package-updater' https://crates.io/api/v1/crates/<name>/<version> | jq -r .version.created_at
```

Go module proxy; a module path escapes each capital letter as `!` plus
the lowercase letter, and the version keeps its `v`:

```console
$ curl -fsS https://proxy.golang.org/<module>/@v/<version>.info | jq -r .Time
```

A tool released on GitHub (just, pnpm, mise, a runtime), using the tag
the project publishes:

```console
$ gh api repos/<owner>/<repo>/releases/tags/<tag> --jq .published_at
```

Node.js, which publishes a date and no time of day. Treat the release as
published at the end of that day (23:59 UTC), so the check errs toward
waiting:

```console
$ curl -fsS https://nodejs.org/dist/index.json | jq -r '.[] | select(.version=="v<version>") | .date'
```
