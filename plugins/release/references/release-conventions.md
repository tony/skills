# Release conventions reference

Discovery procedures and templates for `/release:cut` and
`/release:bump`. Discover everything from the target repo at runtime;
assume nothing about language or ecosystem. The push and tag safety
contract lives in `/release:cut`.

## Contents

- Version-bearing files
- Version schemes
- CHANGES
- MIGRATION
- Release commit
- Sources

## Version-bearing files

Scan the repo root for manifests, in order of precedence:

- `pyproject.toml`: `[project] version`. Workspace repos may repeat
  the version in `packages/*/pyproject.toml`.
- `src/<pkg>/__about__.py` (or `<pkg>/__about__.py`): a `__version__`
  string. Many projects re-export it from `__init__.py`
  (`from .__about__ import __version__`); the re-export needs no edit.
- `package.json`: `version`, possibly per-package in a workspace
  (`packages/*/package.json`).
- `Cargo.toml`: `[package] version`.
- A bare `VERSION` file.

Then find stray version literals the manifest scan misses:

```console
$ rg -n -F --hidden \
    -g '!.git' \
    -g '!*.lock' \
    -g '!package-lock.json' \
    -g '!pnpm-lock.yaml' \
    '<current-version>' \
    .
```

Include a stray literal in the bump only when it clearly tracks the
release version (a Sphinx `setup()` return dict, a test expectation, a
CLI `--version` fallback). Leave coincidental matches alone.

### Bump tooling

Prefer the project's own bump tooling only after verifying an edit-only path:

- A `justfile` / `Makefile` recipe such as `bump-version <version>`
- A `scripts/` bump script referenced by that recipe
- Ecosystem tools the project demonstrably uses (`npm version`,
  changesets, `cargo set-version`, which comes from the cargo-edit
  extension and is not part of cargo)

Inspect the selected recipe, commands it invokes, lifecycle scripts and effective
options before execution. Before the release commit, bump, lock and quality-gate
commands must not commit, create or move tags, push refs, or publish artifacts.
`npm version` commits and tags by default, and runs the project's `preversion`,
`version` and `postversion` scripts.
Git operations confined to fresh, run-owned offline test repositories are
permitted; their writes must stay inside those fixtures.
The user's tag/push flags authorize later steps, not these early side effects.

Use a documented edit-only mode only when its invoked scripts also satisfy this
boundary. A tool's no-tag option need not suppress lifecycle scripts; those
scripts may publish independently. Preserve required generation and validation,
Git hooks and signing policy; do not disable them to make a command appear safe.

If no verified edit-only path exists, edit the discovered version files directly
and run only the project's supported nonpublishing generation and lock steps.
If their effects cannot be established or required work cannot be preserved,
stop before running the command and ask for the project's release procedure.

Record the chosen command and inspected inputs, then recheck those inputs before
execution. Observe HEAD, refs, index and working changes after each command;
unexpected effects stop later steps and remain available for inspection. Do not
reset, retag or retry to hide them. These observations detect drift; they do not
make an opaque command safe to run.

### Lockfiles

Never hand-edit a lockfile. After bumping the manifest, refresh with
the ecosystem's lock command (`uv lock`, `npm install
--package-lock-only`, `pnpm install --lockfile-only`, `cargo update
--workspace`, ...; see Sources). The lockfile refresh belongs in the same release
commit as the version bump. Inspect the command's scripts and options under the
bump-tooling boundary before running it.

## Version schemes

Classify the project's scheme from its current version and its tags.
`release_plan.py` orders versions and tags (`compare`, `tags`, `candidates`).
Never rely on `git tag --sort=-version:refname`: git sorts a tag with a
suffix after the same version without one, so `v1.0.0-rc.1` lists above
`v1.0.0` unless `versionsort.suffix` is set.

- **PEP 440 prerelease track**: `0.0.1a35`, `0.1.0a41`. Increments:
  next prerelease (`a35` → `a36`), segment promotion (`a` → `b` →
  `rc`), graduation to final (`0.0.1a35` → `0.0.1`).
- **Stable semver**: `0.1.9`, `1.74.0`. Increments: patch
  (`0.1.9` → `0.1.10`), minor (`0.1.9` → `0.2.0`), major
  (`0.1.9` → `1.0.0`). A SemVer prerelease joins the identifier with a
  hyphen: `0.2.0-rc.1`.
- **PEP 440 series start**: a stable PEP 440 project begins a prerelease
  series without a hyphen: `0.1.9` → `0.2.0a0`.
- **npm prerelease**: `0.1.0-next.11` → `0.1.0-next.12`, or
  graduation to `0.1.0`.

Mirror the vocabulary the project has actually used in its tags. Do
not introduce `rc`/`post`/`dev` segments into a project whose history
never used them unless the user asks.

Tags are usually `v`-prefixed (`v0.62.0`); `release_plan.py tags` reports the
prefixes the repo uses. `<tag>` is that prefix plus the version.

## CHANGES

Find the changelog: `CHANGES`, `CHANGES.md`, `CHANGELOG`,
`CHANGELOG.md`, `HISTORY`, `NEWS` (prefer the populated one). The
existing file is the source of truth for shape; mirror it exactly.

### Unreleased header

Detect the project's variant:

```markdown
## <project> 0.63.x (Yet to be released)
```

```markdown
## <project> 0.46.x (unreleased)
```

```markdown
## <project> 0.0.1a36 (unreleased)
```

Stable-track projects target `MAJOR.MINOR.x` for the next unreleased
version, since the patch number is unknowable in advance; after cutting
`1.70.1` the placeholder usually reads `1.71.x`; `release_plan.py next-target`
computes that default, and the file's own past release-to-placeholder
transitions override it. Prerelease-track
projects target the full next prerelease (after `0.0.1a35`, `0.0.1a36`).
Mirror a `v` prefix in the header if the project uses one.

Below the header, projects keep a maintainer comment and placeholder
block. Preserve the exact wording found in the file, for example:

```markdown
<!-- To maintainers and contributors: Please add notes for the forthcoming version below -->

<!-- KEEP THIS PLACEHOLDER - DO NOT REMOVE OR MODIFY THIS LINE -->
_Notes on the upcoming release will go here._
<!-- END PLACEHOLDER - ADD NEW CHANGELOG ENTRIES BELOW THIS LINE -->
```

### Releasing a section

At release time:

1. Retitle the unreleased header to the concrete version with today's
   date (`date +%Y-%m-%d`), in the shape the file's released headings
   use; with no precedent, `## <project> <version> (YYYY-MM-DD)`.
2. Remove the maintainer comment and placeholder lines from the
   now-released section (they move up, not stay behind).
3. If the project's released sections open with a short prose lead
   paragraph summarizing the release at a product level, write one
   from the section's entries.
4. Insert a fresh unreleased block above it, with a header targeting the
   next version per the rule above, with the same maintainer comment
   and placeholder block.

## MIGRATION

If a `MIGRATION` file exists, it follows the same lifecycle:

- Unreleased entries live under a `## Next release` heading, or under
  version-ranged headings like `## <project> 0.62.x: <title> (#NN)`.
- At release, retitle: `0.62.x` becomes the concrete version; a
  `## Next release` placeholder is re-inserted if that is the
  project's pattern. Mirror the file's own precedent.

## Release commit

The subject is plain, never the `Scope(type[detail])` format:

```
Tag <tag>
```

Body uses the project's convention (why/what blocks or a bullet list),
covering:

```
why: Cut the <version> release: <one-line product summary>.

what:
- Date the <version> CHANGES section (YYYY-MM-DD) and add its lead
  paragraph
- Open a fresh <next> unreleased placeholder
- Bump version <old> -> <version> in <files touched>
- Refresh <lockfile>
```

Add a MIGRATION line when that file was retitled.

No `Co-Authored-By` line, no "Generated with" or other tool trailer, no emoji.

## Sources

- SemVer precedence, including that a prerelease sorts below its release:
  [semver.org](https://semver.org/spec/v2.0.0.html), items 9 and 11.
- PEP 440 ordering, prerelease and post-release segments:
  [PEP 440](https://peps.python.org/pep-0440/).
- Git tag sorting with suffixes:
  [`versionsort.suffix`](https://git-scm.com/docs/git-config).
- `npm version` commits, tags and runs lifecycle scripts:
  [npm version](https://docs.npmjs.com/cli/v10/commands/npm-version).
- Lock refresh:
  [`npm install --package-lock-only`](https://docs.npmjs.com/cli/v10/commands/npm-install),
  [`pnpm install --lockfile-only`](https://pnpm.io/cli/install),
  [`cargo update --workspace`](https://doc.rust-lang.org/cargo/commands/cargo-update.html).
- `cargo set-version`: [cargo-edit](https://github.com/killercup/cargo-edit).
- Yanked releases: [PEP 592](https://peps.python.org/pep-0592/) defines
  yanking per file; the PyPI JSON API reports it as `yanked` and
  `yanked_reason` on each file under `urls`. `downstream_check.py index`
  refuses a release whose files are all yanked.
- npm deprecation: [npm deprecate](https://docs.npmjs.com/cli/v10/commands/npm-deprecate)
  updates the registry entry with a warning; the version document carries it
  as a `deprecated` string, which `index` reports without refusing.
- Index endpoints behind `downstream_check.py index`:
  [PyPI JSON API](https://docs.pypi.org/api/json/),
  [npm registry API](https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md).
- The `gh` commands the downstream rollout runs, as of the version recorded
  in the README prerequisites:
  [`gh run list`](https://cli.github.com/manual/gh_run_list),
  [`gh run watch`](https://cli.github.com/manual/gh_run_watch),
  [`gh run rerun`](https://cli.github.com/manual/gh_run_rerun),
  [`gh cache delete`](https://cli.github.com/manual/gh_cache_delete).
