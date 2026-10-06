# Dependency commit conventions

A dependency commit is read years later by someone deciding whether a
version is safe to move again, so the body carries the reasoning and the
links, not an inventory of the diff.

Defer to the project's own `AGENTS.md` or `CLAUDE.md` when it states a
subject format. What follows is the shape to use when the project does
not say otherwise.

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
.ncurc: <what and why>
```

Follow-ups use the project's own `type(scope)` form, for example
`test(<package>) regenerate snapshots`.

Use an ASCII `->` for a version transition. Keep the subject at 64
characters or fewer.

## The four tracks

Each track has its own commit, and each follow-up and hold change is a
further commit. None are merged, and tracks land in this order within a
session.

### Toolchain and runtime

One tool per commit, even when a single edit to `.tool-versions` moves
three tools. Each bump reverts on its own, and a reader bisecting a
runtime regression needs the tools separated.

A single commit may span several releases of that one tool. When it
does, link every release in the span, not just the endpoint — the
intermediate ones are where the regression usually is.

A routine bump takes a link block and nothing else: a patch or minor
inside the same series, with nothing in the span the repository
exercises, is fully described by its links.

A bump takes a `why:` above that link block when any of these hold:

- It crosses a major, or the vendor labels the release breaking.
- The span changes behavior the repository exercises — a resolver
  default, a discovery rule, a newly rejected input format.
- It carries a security fix.
- A newer release exists and is deliberately skipped, gated by a
  cooldown or held back.

That `why:` answers two questions and stops: what the span changes
upstream, describing the intermediate releases rather than only linking
them; and what those changes reach in *this* repository.

Write the intersection where it survives. Analysis that lands only in
the session report dies with the session — the commit is what a reader
finds in `git log` two years later.

Negatives alone are half a body. "Does not apply, no such files, inert"
proves the bump is safe and says nothing about why it was worth taking.
Name what the repository gains as concretely as what it dodges. When a
span genuinely touches nothing here, one line saying so is the finding.

### Package manager and engines

`packageManager` and `engines` in `package.json` pin the toolchain, so
they move on their own:

```text
js(deps) pnpm <old> -> <new>
js(engines) require Node >=<version>
```

A package-manager bump takes a link block. An `engines` bump takes a
`why:`/`what:` body, because a floor exists for a reason and the reason
is not recoverable from the diff.

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

- The version crosses a major.
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
`ncu -u` with no named package, and `pnpm update` alike. Nothing worth
saying is not already in the lockfile diff, and a generated inventory of
package names is noise that makes the commits that *do* carry reasoning
harder to find. The subject says which kind of refresh it is: manifest
bumps, or in-range transitives with no manifest edit. A package that
needs words (a major, a follow-up, a floor) leaves the bulk refresh and
takes its own commit.

### Catalog and override pins

A version pinned in `pnpm-workspace.yaml` under `catalog:` is invisible
to `ncu`, so it is bumped by hand and scoped to the file it lives in:

```text
js(deps[catalog]) @biomejs/biome 2.5.3 -> 2.5.4
```

Say in the body that the tool missed it. A reader who runs `ncu` and
sees nothing outstanding needs to know why this commit exists.

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

State the cooldown when it is load-bearing — that a release is being
taken now because it cleared the window, or that a newer release exists
and is deliberately excluded because it has not. A reader comparing the
commit against the registry will otherwise think the bump was stale on
arrival.

Never write a claim into a body that has not been checked against the
repository the commit lands in. A fleet-wide fact is not a per-repo
fact, and a false claim committed to history stays false.

Never add a `Co-Authored-By` trailer, a "Generated with" line or other
tool trailer, a tool URL, or an emoji. Hosts add them by default and
they cannot be removed from history without a rewrite.

## Writing the message

Multi-line messages go through a heredoc or a file. Passing a
multi-line string to `git commit -m` through an interactive shell has
collapsed bodies into the subject line, producing commits whose subject
runs to several hundred characters with the link block inlined.

```bash
git commit -F - <<'EOF'
js(deps[dev]) @biomejs/biome 2.5.3 -> 2.5.4

why: Track latest Biome patch release (published <date>, now past
the <N>-day supply-chain cooldown).

what:
- Bump @biomejs/biome in root, lib, wc (exact) and site (caret)
- Lockfile: biome + platform CLI binaries 2.5.3 -> 2.5.4
EOF
```

## Exemplars

Match their density, not their length.

A named bump whose body earns its place by naming the coupling:

```text
js(deps) Astro 7.0.9 + MDX 7.0.3 + Satteri 0.3.4

why: These ship as one release train: astro 7.0.8 bundles
markdown-satteri 0.3.4, and @astrojs/mdx 7.0.3's highlighter contract
(codeToHast) matches satteri 0.3.4 despite the loose ^0.3.1 peer
range (upstream PR #17341), so bumping them together keeps the
resolved graph coherent.

what:
- astro ^7.0.7 -> ^7.0.9 (compiler-rs 0.3.1 slot/client:only fixes,
  dev-server no longer full-reloads first visit, island hydration
  retry fix)
- @astrojs/mdx ^7.0.2 -> ^7.0.3 (custom `pre` components reach
  highlighted code blocks; inert here — expressive-code owns blocks)
- @astrojs/markdown-satteri ^0.3.3 -> ^0.3.4 (codeToHast switch,
  drops makeFragmentNode export and plugin `mdx` option)
- astro 7.1.1 exists but stays excluded by the 3-day release cooldown
```

A routine toolchain bump, link block only:

```text
.tool-versions(just) just 1.55.1 -> 1.57.0

- just
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
