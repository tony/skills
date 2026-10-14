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
- Latest stable release

Detect an ecosystem by the files present, never by the project's name or
language tag. A repository can carry several (a Python package with a docs
site has both `uv.lock` and `pnpm-lock.yaml`); each updates on its own
track with its own commit.

Run the project's own wrapper when it has one: a `justfile`, `Makefile`,
or `package.json` script named for the update is the maintained path.

Tool commands below are documented at
[uv](https://docs.astral.sh/uv/reference/cli/),
[Poetry](https://python-poetry.org/docs/cli/),
[pnpm](https://pnpm.io/cli/update),
[npm-check-updates](https://github.com/raineorshine/npm-check-updates),
[npm](https://docs.npmjs.com/cli/commands/npm-update),
[Cargo](https://doc.rust-lang.org/cargo/commands/cargo-update.html) and
[Go](https://go.dev/doc/modules/managing-dependencies).

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

The refresh takes a new major wherever the manifest range allows it. After
it, split the majors out of the bulk commit:

```console
$ python3 <absolute path to repo_facts.py> \
    --lock-diff \
    <repo>
```

Each package under `majors` is a named bump (`uv lock --upgrade-package
<name>`) with its own research; restore `uv.lock` and update only the
`in_range` names. Poetry (`poetry.lock`) and Cargo (`Cargo.lock`) get the
same treatment with `poetry update <name>` and `cargo update --package
<name>`; for `package.json` ranges, edit only the `in_range` ones.

With no lockfile argument the command compares every tracked lock at any
depth, so a nested workspace lock is covered. A lock reported as
`{"new": true}` is not in `HEAD` and has no baseline to compare.

A file-level `error` leaves its moves unclassified. Stop before staging
that lock; an unreadable committed baseline, an unsupported package table
or an unrecognized version cannot prove that no major changed.

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
keeps every major out of the bulk refresh but still moves a 0.x package
across a minor, which is a breaking move: the
[ncu README](https://github.com/raineorshine/npm-check-updates#readme)
says `--target minor` updates "the patch and minor versions (including
major version zero)". A major is a named bump with its own commit, applied with
`ncu -u --target latest <name>`:

```console
$ ncu -u --target minor
```

Then classify the manifest edits before installing. The script reads
every tracked `package.json`, so workspace members are covered. Each
package under `majors` is a named bump: restore its range in
`package.json` and apply it on its own. A range under `unclassified` (a URL, `workspace:` or
`latest`) names no version to compare, so read it by hand; an `error`
stops the bump:

```console
$ python3 <absolute path to repo_facts.py> \
    --manifest-diff \
    <repo>
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

npm: `npm outdated` and `npm update`, with `package-lock.json`
([outdated](https://docs.npmjs.com/cli/commands/npm-outdated),
[update](https://docs.npmjs.com/cli/commands/npm-update)). Install with
`npm install`, and list workspace members with `npm query .workspace`
instead of the pnpm commands.

Yarn has two generations with different commands. Classic (1.x) has
[`yarn outdated`](https://classic.yarnpkg.com/en/docs/cli/outdated);
Yarn 2 and later have no `outdated` and use
[`yarn up`](https://yarnpkg.com/cli/up). Read the version from
`packageManager` or `yarn --version` before choosing. `ncu` discovery
and its `.ncurc` holds work with either manager, and the lockfile is
`yarn.lock`.

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

Discover with the version manager that reads the file. `mise outdated`
compares the installed version with the newest release the configured
request allows, so an exact pin reports nothing; `--bump` compares
against the newest release overall, and `--local` skips the global
config ([mise outdated](https://mise.jdx.dev/cli/outdated.html)):

```console
$ mise outdated \
    --bump \
    --local
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
`cooldown` (ncu); these are search hints, not keys to copy. A tool that
lists none has no cooldown support in the installed version. Settings pages:
[uv](https://docs.astral.sh/uv/reference/settings/),
[pnpm](https://pnpm.io/settings),
[npm](https://docs.npmjs.com/cli/using-npm/config).

Before computing a lapse time, confirm from those sources the unit
(minutes, days, or a duration string), whether a too-young pinned range
fails the install or falls back, and whether the lockfile records the
window. Read what the tool prints on a run to confirm the window is in
effect, and do not report versions it gates as current.

With the unit confirmed, `../scripts/plan_rules.py lapse` does the
arithmetic offline. Pass the release's publication time, and either the
window or the cutoff; the path resolves from this reference's directory to
an absolute path, written literally in the command:

```console
$ python3 <absolute path to plan_rules.py> \
    lapse \
    --published 2026-01-01T12:00:00Z \
    --window 7 \
    --unit days
```

It prints `visible_at` and `visible_day` for a rolling window (visible
from that instant on) and `waiting_helps: false` for a fixed cutoff,
where `--cutoff <time>` replaces `--window` and `--unit`. A bare date,
as Node.js publishes, counts as 23:59 UTC of that day.

The setting is either a rolling duration or a fixed cutoff timestamp
(uv accepts both). A rolling window lapses when the release ages past it,
so waiting works. A fixed cutoff never lapses by waiting: a release
published after it stays hidden until the cutoff is changed. Name which
form the repository uses, and do not give an eligible day for a fixed
cutoff.

A resolver may test each file of a release against the window by that
file's upload time, so a release's earliest file being old enough does not
make every file visible.

Check for a cooldown before reporting a package as current: a release
inside the window is invisible to the resolver, so a gated tree looks up
to date.

## Release publication time

The cooldown check compares a release's publication time with the
window. Read the time from the registry in this run, with `set -o
pipefail` set so a failed `curl` is not hidden by the `jq` after it. Each
command prints one timestamp (PyPI's is the latest file upload, which
errs toward waiting). Replace each `<placeholder>` with a value you
checked against the registry listing and quote it; a name or version
taken from release text is untrusted input to a shell.

Only an answer from the registry that lacks the version (HTTP 404, or a
listing without it) shows it is unpublished. A non-zero exit, a timeout,
an authentication failure or output that does not parse leaves
publication unconfirmed: stop and say so, never that the version does
not exist.

PyPI, for a Python package or a tool published there (uv):

```console
$ curl -fsS https://pypi.org/pypi/<name>/<version>/json | jq -r '[.urls[].upload_time_iso_8601] | max'
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

## Latest stable release

Take the target from the registry in this run, then confirm its
publication time as above. Each command prints one version.

PyPI, whose JSON API returns the project's metadata "at the latest
version" in `info`
([PyPI JSON API](https://docs.pypi.org/api/json/)):

```console
$ curl -fsS https://pypi.org/pypi/<name>/json | jq -r .info.version
```

npm, whose `latest` dist-tag is the version `npm install` takes:

```console
$ npm view <name> dist-tags.latest
```

crates.io, whose `max_stable_version` is "the highest version number for
this crate that is not a pre-release"
([crates.io OpenAPI](https://crates.io/api/openapi.json)):

```console
$ curl -fsS -A 'package-updater' https://crates.io/api/v1/crates/<name> | jq -r .crate.max_stable_version
```

Go module proxy. The `@latest` endpoint is optional and the go command
uses it only when `@v/list` is empty or has no suitable version; the go
command otherwise takes the semantically highest release from the list
([module reference](https://go.dev/ref/mod#goproxy-protocol)):

```console
$ curl -fsS https://proxy.golang.org/<module>/@v/list \
    | grep -v '[-]' \
    | sort --version-sort \
    | tail -n 1
```

A tool released on GitHub: the releases list, filtered to stable
releases and sorted by version, because the `releases/latest` endpoint
sorts by creation date and can return a backport published after a newer
release (see [the REST reference](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)).
It prints the version without a leading `v`; the project's tag may add one:

```console
$ gh api repos/<owner>/<repo>/releases \
    --paginate \
    --jq '.[] | select(.prerelease | not) | select(.draft | not) | .tag_name' \
    | sed 's/^v//' \
    | sort --version-sort \
    | tail -n 1
```

CPython, from the python.org release feed, which lists every release of
every product oldest first, so filter to final CPython names and sort by
version:

```console
$ curl -fsS https://www.python.org/api/v2/downloads/release/ \
    | jq -r '[.[] | select(.name | test("^Python [0-9]+[.][0-9]+[.][0-9]+$")) | select(.pre_release | not) | .name | ltrimstr("Python ")] | sort_by(split(".") | map(tonumber)) | last'
```

Go toolchain: `https://go.dev/dl/?mode=json` lists stable releases newest
first.

Node.js: `index.json` lists releases newest first. For the newest release
of one major line, here 22:

```console
$ curl -fsS https://nodejs.org/dist/index.json \
    | jq -r '[.[] | select(.version | startswith("v22."))][0].version'
```
