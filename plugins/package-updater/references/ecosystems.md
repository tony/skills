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

Detect an ecosystem by the files present, never by the project's name or
its language tag. A repository can carry several at once — a Python
package with a docs site has both `uv.lock` and `pnpm-lock.yaml`, and
each one updates on its own track with its own commit.

Run the project's own wrapper when it has one. A `justfile`, `Makefile`,
or `package.json` script named for the update is the maintained path,
and it may do more than the raw command below.

## Python with uv

Marked by `uv.lock` beside `pyproject.toml`.

Discovery and apply are usually one step here — the upgrade resolves and
reports in the same run, and the lockfile diff is the report. Use a
separate discovery pass when you need to decide before writing:

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

The lockfile is `uv.lock` and it is the only artifact the bulk refresh
commits. Confirm the lock actually moved rather than assuming the
constraint was enough — a floor raised in `pyproject.toml` does nothing
until the resolver rewrites the lock.

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

**Apply** the manifest bump, then install:

```console
$ ncu -u
```

```console
$ pnpm install
```

`ncu -u` acts on the manifest in the current directory unless told
otherwise. Confirm the workspace options with `ncu --help`, or recurse
to the members:

```console
$ pnpm --recursive exec ncu -u
```

Projects that do this often wrap both halves in a script — an
`update:all` that runs `ncu -u` at the root and then recursively. Use
the project's script when it has one.

**Apply** an in-range refresh, which moves transitives without touching
any manifest:

```console
$ pnpm update
```

Those are two different commits with two different meanings. `ncu -u`
edits `package.json` and lands as a dependency bump; `pnpm update` edits
only the lockfile and lands as an in-range transitive refresh.

### Clean reinstall

Not part of the routine apply: `pnpm install` reconciles the tree
itself. Reach for a clean reinstall only when an install fails or leaves
a stale tree, and treat it as destructive. Put it in the plan, name the
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
`catalog:` is not in any `package.json`, so `ncu` never reports it.
Check the catalog by hand on every sweep, or the workspace silently
stops tracking its own pinned tools.

**Overrides and resolutions.** Same problem, same fix.

### Holding a package back

`.ncurc` carries a `reject` array of packages `ncu` must not offer. It
resolves next to the package file, so a workspace member can hold a
package its siblings track — a root-only scan under-reports holds.

Adding and releasing a hold are both commits, and both name the
condition. The reason cannot be written into the file itself, because
`ncu` rejects unknown keys; the commit message carries it.

For a one-off exclusion that is not worth checking in, `ncu -u -x <name>`.

## Node with npm or yarn

`npm outdated` and `npm update`; `yarn outdated` and `yarn up`. The
lockfile is `package-lock.json` or `yarn.lock`. Everything else in the
pnpm section applies unchanged, except the cooldown key.

## Rust

Marked by `Cargo.lock`.

Do not run `cargo-outdated` (the skill body states why). Discover with
the resolver instead:

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

Poetry, pip and Go commands above come from the tools' own
documentation, not from a procedure the project has settled on. Say so
in the plan, propose the command, and let the user confirm before the
first run in that repository.

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

A cooldown makes the resolver ignore releases younger than a threshold,
which limits exposure to compromised uploads that get yanked within
hours. Each ecosystem configures it with its own key, unit, and
strictness, and those change between releases. Read them from the
installed tool before relying on one, and do not copy a key or unit from
another repository's config.

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
`cooldown` (ncu). A tool that lists none has no cooldown support in the
installed version. Settings pages:
[uv](https://docs.astral.sh/uv/reference/settings/),
[pnpm](https://pnpm.io/settings),
[npm](https://docs.npmjs.com/cli/using-npm/config).

Before computing a lapse time, confirm from those sources the unit
(minutes, days, or a duration string), whether a too-young pinned range
fails the install or falls back, and whether the lockfile records the
window. Read what the tool prints on a run to confirm the window is in
effect, and do not report versions it gates as current.

Check for a cooldown before reporting a package as current. A release
published inside the window is invisible to the resolver, so an update
run that does not know this reports the tree as up to date when it is
merely gated.

### Exempting a package

Only when the resolver cannot see a release that is needed now. An
exemption is a hole in a supply-chain guard, so keep it small and
temporary. Skip it when the resolver already sees the release or the
window is short enough to wait out.

- Exempt the one package, never the cooldown globally. Use the
  per-package override the tool documents; a tool with none means waiting.
- Prefer an override form that carries no date. A dated override ages
  into the lockfile and stops meaning anything.
- Annotate it in the file with the reason and the condition for removal.
  JSON configs reject comments: put the annotation in the commit message
  instead.
- Land it as its own commit, first in the branch, so one revert removes
  it.
- Compute when the block lapses (publication timestamp plus the window),
  state it in the commit body, and revert the exemption then.
- When the work goes through a pull request, name the revert as a
  pre-merge requirement in its body, with the lapse time.
