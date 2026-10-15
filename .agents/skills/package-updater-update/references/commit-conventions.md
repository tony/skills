# Dependency commit conventions

The body carries the reasoning and the links, not an inventory of the
diff. Defer to the project's own `AGENTS.md` or `CLAUDE.md` when it
states a subject format; what follows applies when it does not.

## Contents

- Subject grammar
- The four tracks
- Body anatomy
- Writing the message
- Exemplars

## Subject grammar

Three forms cover every commit this plugin writes.

Dependencies, in the ecosystem's scope:

```text
<scope>(deps[<group>]) <what moved>
```

The scope names the ecosystem, not the tool: `py` for Python, `js` for
JavaScript and TypeScript, `rs`, `go`. The bracketed group names the
dependency group the change lands in (`dev`, `docs`, `lint`, `catalog`)
and is omitted when the change is not scoped to one. `packageManager`
and `engines` take this form too, with `deps` and `engines` as the
keyword.

Toolchain version files and config files, scoped by the file, because
the file is what the reader greps for:

```text
.tool-versions(<tool>) <tool> <old> -> <new>
.nvmrc(nodejs) <old> -> <new>
.python-version(python) <old> -> <new>
mise.toml(<tool>) <tool> <old> -> <new>
.ncurc: <what and why>
```

Follow-ups use the project's own `type(scope)` form, for example
`test(<package>) regenerate snapshots`.

Use an ASCII `->` for a version transition. Keep the subject at 64
characters or fewer.

## The four tracks

Each track has its own commit, as does each follow-up and hold change.
Tracks land in this order within a session.

### Toolchain and runtime

One tool per commit, even when a single edit to `.tool-versions` moves
three tools. A commit may span several releases of that one tool; link
every release in the span, not just the endpoint.

A routine bump takes a link block and nothing else: a patch or minor
inside the same series, with nothing in the span the repository
exercises, is fully described by its links.

A bump takes a `why:` above that link block when any of these hold:

- It crosses a major (for a 0.x tool, a minor, which may break), or the
  vendor labels the release breaking.
- The span changes behavior the repository exercises: a resolver
  default, a discovery rule, a newly rejected input format.
- It carries a security fix.
- A newer release exists and is deliberately skipped, gated by a
  cooldown or held back.

That `why:` answers two questions and stops: what the span changes
upstream, describing the intermediate releases rather than only linking
them; and what those changes reach in *this* repository.

Write the intersection in the commit; analysis left in the session
report dies with the session.

Negatives alone are half a body. "Does not apply, inert" says nothing
about why the bump was worth taking. Name what the repository gains as
concretely as what it dodges. When a span touches nothing here, one line
saying so is the finding.

### Package manager and engines

`packageManager` and `engines` in `package.json` pin the toolchain, so
they move on their own:

```text
js(deps) pnpm <old> -> <new>
js(engines) require Node >=<version>
```

A package-manager bump takes a link block. An `engines` bump takes a
`why:`/`what:` body: the reason for a floor is not in the diff.

### Named package bumps

One commit per package, or per release train when packages must move
together. A release train needs the body to say *why* they are coupled
(a peer contract, a bundled dependency, a shared compiler), otherwise the
next reader will split them.

The body is `why:` then `what:`. The `why:` explains what the release
changes for *this* repository; the `what:` lists the manifests touched
and what the lockfile did. Close with links when the release notes are
worth reaching.

A package earns its own commit when any of these hold:

- The version crosses a major, or for a 0.x package a minor, which is
  where 0.x breaks.
- It is a linter, formatter, or compiler whose output changes.
- It needs a follow-up commit.
- The change is a floor or constraint in the manifest, not just a
  lockfile move.
- It is a workspace sibling this repository also publishes.
- It carries a security fix.

Everything else belongs in the bulk refresh.

### Bulk lockfile refresh

```text
py(deps[dev]) Bump dev packages
js(deps[dev]) Bump dev packages
js(deps) Refresh in-range transitives
```

**The body is empty,** for every ecosystem: `uv sync --upgrade`,
`ncu -u --target minor` with no named package, and `pnpm update`
alike. The lockfile
diff already says it, and a generated package inventory buries the
commits that carry reasoning. The subject says which kind of refresh it
is: manifest bumps, or in-range transitives with no manifest edit. A
package that needs words (a major, a follow-up, a floor) takes its own
commit.

### Catalog and override pins

A version pinned in `pnpm-workspace.yaml` under `catalog:` is invisible
to `ncu`, so it is bumped by hand and scoped to the file it lives in:

```text
js(deps[catalog]) @biomejs/biome 2.5.3 -> 2.5.4
```

Say in the body that the tool missed it, so a reader who runs `ncu` and
sees nothing outstanding knows why the commit exists.

## Body anatomy

Wrap body lines at 72 characters. Separate `why:` and `what:` with a
blank line.

### Link blocks

Style follows link count, not preference.

**One link** goes inline on a single line:

```text
See also: https://nodejs.org/en/blog/release/v25.2.0
```

**Two or more** put `See also:` on its own line, then one hyphen bullet
per URL:

```text
See also:
- https://pnpm.io/blog/releases/11.17
- https://github.com/pnpm/pnpm/releases/tag/v11.17.0
```

When a commit moves more than one tool, group the bullets under the tool
they belong to, so a reader chasing one of them is not sorting URLs by
hostname.

### Cooldown

State the cooldown when it is load-bearing: a release taken now because
it cleared the window, or a newer release deliberately excluded because
it has not, so the commit does not read as stale against the registry.

Never write a claim into a body that was not checked against the
repository the commit lands in; a fleet-wide fact is not a per-repo fact.

Never add a `Co-Authored-By` trailer, a "Generated with" line or other
tool trailer, a tool URL, or an emoji. Hosts add them by default.

## Writing the message

Multi-line messages go through a heredoc or a file; a multi-line
`git commit -m` string has collapsed bodies into the subject line. A body
built from release-note text is untrusted: write it to a file with the
file-writing tool and run `git commit -F <file>`. A message the skill
authors itself may use a quoted heredoc, with a delimiter that appears
nowhere in the body (check before running).

```console
$ git commit -F - <<'COMMIT_MSG_END'
js(deps[dev]) @biomejs/biome 2.5.3 -> 2.5.4

why: Track latest Biome patch release (published <date>, now past
the <N>-day supply-chain cooldown).

what:
- Bump @biomejs/biome in root, lib, wc (exact) and site (caret)
- Lockfile: biome + platform CLI binaries 2.5.3 -> 2.5.4
COMMIT_MSG_END
```

## Exemplars

Match their density, not their length. Versions, issue numbers and
vendor behavior in them are invented for illustration; never copy one
into a real body.

A named bump whose body earns its place by naming the coupling:

```text
js(deps) Astro 7.0.9 + MDX 7.0.3 + Satteri 0.3.4

why: These ship as one release train: astro 7.0.8 bundles
markdown-satteri 0.3.4, and @astrojs/mdx 7.0.3's highlighter contract
(codeToHast) matches satteri 0.3.4 despite the loose ^0.3.1 peer
range (upstream PR #<number>), so bumping them together keeps the
resolved graph coherent.

what:
- astro ^7.0.7 -> ^7.0.9 (the span's fixes that reach this site)
- @astrojs/mdx ^7.0.2 -> ^7.0.3 (a change in the span that is inert
  here, and why)
- @astrojs/markdown-satteri ^0.3.3 -> ^0.3.4 (the API change that
  forced the coupling)
- astro 7.1.1 exists but stays excluded by the 3-day release cooldown
```

A routine toolchain bump, link block only:

```text
.tool-versions(just) just 1.55.1 -> 1.57.0

See also:
- https://github.com/casey/just/blob/1.57.0/CHANGELOG.md
- https://github.com/casey/just/releases/tag/1.56.0
- https://github.com/casey/just/releases/tag/1.57.0
```

A drift consolidation, where the reason is the drift itself:

```text
js(deps[dev]) Unify Biome to 2.5.3

why: Biome versions had drifted (2.4.16 in colors +
vite-plugin-webfont-preload, 2.5.2 elsewhere). A single version keeps
lint/format behavior identical across packages and collapses two copies
of the toolchain (+ platform binaries) in the lockfile into one.

what:
- Bump @biomejs/biome to 2.5.3 in root + 7 packages
- biome migrate: config $schema 2.5.2 -> 2.5.3
- Consolidate two Biome versions to one in pnpm-lock.yaml
- No new diagnostics: biome lint/check/format all clean
```
