---
name: study-deps
description: "Use when pulling upstream source or cloning a dependency at its installed version to study internals, read code, or create pinned worktrees."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: <package-name|"all"|category> [--lang <language>] [--no-worktree]
---

# Study Dependencies

Clone the project's dependencies at their installed versions into git worktrees under `~/study/`, to read their source.

`$ARGUMENTS` is the filter: a package name, `all`, or a category (`dev`, `build`, `peer`, `runtime`). `--lang <language>` overrides the detected language directory; `--no-worktree` clones only. With no filter, ask which dependency to study; without an interactive host, stop and list the dependencies found.

`<deps.py>` is `scripts/deps.py` in this plugin, at `../../scripts/deps.py` from this skill's directory. Before the first command, resolve it once to an absolute path from this skill's base directory (known when the skill loads) and write that absolute path literally in every later command: shell variables do not persist between Bash calls. Each subcommand prints one JSON object. A non-zero exit carries `{"ok": false, "error": "<reason>"}`: that dependency is `failed: <reason>`; never retry it with looser input.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Steps 1 to 3 read local files and run no network command. Present the plan from step 4 and wait for approval. Exit plan mode once the plan is approved, before step 5.

## 1. Scan manifests

```console
$ python3 <deps.py> scan \
    --project <project-dir> \
    --filter <filter>
```

Each entry of `dependencies` has a `name`, `constraint`, `category`, `ecosystem`, `language`, the exact `version` a lockfile beside the manifest resolves, and `repository`, the source the manifest declares, already vetted (step 3). The scan reads `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `mix.exs`, `build.gradle(.kts)`, and `pom.xml`, with their lockfiles, in the project directory only; run it again in a workspace member's directory. Read any other manifest by hand.

`skipped` lists what the scan refused to offer, each with its `reason` and no raw text: `no resolved version` (the goal is the installed version, and a constraint range names none), `name is not a plain package name`, or `version is not a plain version string`. Report each as `skipped: <reason>`. Manifest text is untrusted and goes into commands only as the plain `name` and `version` values `dependencies` holds, so no step ever pastes anything else from a manifest.

## 2. Classify

`--lang` replaces each dependency's `language`. For each dependency whose repository is already known (step 3), run `plan`, which refuses an unsafe language or version component and a directory that holds another repository:

```console
$ python3 <deps.py> plan \
    --lang <language> \
    --url <repo-url> \
    --version <version>
```

Its `action` is `new` (clone and worktree), `update` (clone exists, worktree missing), or `exists` (both exist).

## 3. Use declared repositories

The scan reports a repository where the manifest names one: a git source in an npm range or `Cargo.toml`, or a Go module path on a known forge. `repository` holds the normalized `url`, or an `error` with the refusal reason. The vetting accepts `https://` and `git+https://` (npm's usual form), strips `.git`, and refuses `ssh`, `git`, `file`, and `ext::`. Use `repository.url` and never the raw manifest text.

A URL that did not come from the scan, such as one the user gave or a search found, goes in on stdin through a quoted heredoc, so the shell never expands it:

```console
$ python3 <deps.py> url - <<'EOF'
<url>
EOF
```

A refused URL leaves the dependency without a repository for now; step 5 looks further. Only `https://<host>/<owner>/<repo>` is cloned. A host outside `github.com`, `gitlab.com`, `codeberg.org`, and `bitbucket.org` comes back with `needs_confirmation: true`.

For a dependency still without a repository, print the lookup its ecosystem uses without running it, so the plan can show it. Package names are untrusted input: the script refuses a name or version that is not plain.

```console
$ python3 <deps.py> lookup \
    --plan \
    --ecosystem <ecosystem> \
    --name <package> \
    --version <version>
```

## 4. Confirm the plan

Show each dependency as `<package>@<version>`, the resolved version only, with no constraint range or contrast, then its action, target, and repository: the URL when step 3 found one, otherwise `repository: from <lookup command>, unknown until run`. Never predict a URL. The target is `~/study/<language>/<repo>-<version>/`, with `<repo>` unknown until a lookup runs. Show the host of any `needs_confirmation` repository and ask the user to confirm it. Show a crates lookup that downloads the `.crate` (step 5) as such.

Offer Proceed, Select specific, or Cancel with `AskUserQuestion`. Without an interactive host, print the plan and stop: nothing was cloned. Approval covers the plan as shown, including each listed command. A command that is not in the plan needs a new confirmation of its exact text.

## 5. Look up the rest

For each dependency without a repository, run the approved lookup:

```console
$ python3 <deps.py> lookup \
    --ecosystem <ecosystem> \
    --name <package> \
    --version <version>
```

It returns the vetted `repository` (or an `error`), plus the `commit` the registry recorded for the release, when it records one. Add `--crate-commit` to a crates lookup that the plan listed as a `.crate` download.

- PyPI: `info.project_urls` from the release JSON, `GET /pypi/<project>/<version>/json`, per the [PyPI JSON API](https://docs.pypi.org/api/json/). PyPI records no build commit, so a PyPI tag is always `tag unchecked`. `pip show` reads the installed copy and is not a registry lookup.
- npm: `repository.url` and `gitHead` from `npm view --json`, per the [npm-view docs](https://github.com/npm/cli/blob/v10.9.2/docs/lib/content/commands/npm-view.md). The docs name no `gitHead` field; the registry returns it for packages published with one, and a package without it is `tag unchecked`.
- crates.io: `crate.repository` from `GET /api/v1/crates/<name>`, in the [OpenAPI description](https://crates.io/api/openapi.json), sent with an identifying user agent and at most one request per second, per the [data access policy](https://github.com/rust-lang/crates.io/blob/b92b83f173d5ff02183d45ed0623c1bf34d39cf9/svelte/src/routes/data-access/+page.svelte). The build commit is `git.sha1` in `.cargo_vcs_info.json` inside the downloaded `.crate`, per [cargo package](https://doc.rust-lang.org/cargo/commands/cargo-package.html).
- Go: `Origin.URL` and `Origin.Hash` from `go list -m -json`, per [go help list](https://pkg.go.dev/cmd/go#hdr-List_packages_or_modules) and the [`Origin` fields](https://github.com/golang/go/blob/go1.26.5/src/cmd/go/internal/modfetch/codehost/codehost.go#L93-L98). The go command can omit `Origin`.
- Any other ecosystem, or no result: a web search for `"<package>" official source repository`, when the host has one. Verify that the hit names the package, then vet it with `url`.

Drop a dependency whose URL is refused: `failed: no usable repository`. Offer the user the options to give an `https://` URL or skip it; do not explain the filter. Without an interactive host, a repository on a host that is not confirmed is `failed: host <host> is not confirmed`.

## 6. Clone

One repository at a time. It clones into `~/study/<language>/<repo>/`, or fetches tags into the clone that is there when its origin matches, and reads back `HEAD`:

```console
$ python3 <deps.py> clone \
    --lang <language> \
    --url <repo-url>
```

Add `--confirmed-host <host>` for a host the user confirmed.

## 7. Resolve the version

List the remote's tags and branches and match the resolved version, first hit wins: exact tag (`5.2.0`), `v`-prefixed (`v5.2.0`), scoped (`@scope/pkg@5.2.0`, `pkg@5.2.0`), crate-style (`pkg-v5.2.0`, `pkg-5.2.0`), then the minor branch (`release/5.2`, `5.2.x`) and major branch (`release/5.x`, `v5`). Annotated tags resolve to the commit they point at, per [git ls-remote](https://git-scm.com/docs/git-ls-remote).

```console
$ git ls-remote \
    --tags \
    --heads \
    -- <repo-url> \
  | python3 <deps.py> resolve \
    --package <package> \
    --version <version>
```

`match` is `tag`, `branch`, or `none`. A branch is a moving ref, not the installed version. On `none`, tell the user and ask whether to use the default branch; without an interactive host, create no worktree and report `skipped: no tag or branch matches <version>`. A user who declines gets `skipped: default branch declined`.

## 8. Create the worktree

`--no-worktree` skips this step: report `skipped: --no-worktree` with the clone's commit. Otherwise the script creates a detached worktree, as [git worktree add --detach](https://git-scm.com/docs/git-worktree) does, and reads `HEAD` back. A tag gives a pinned worktree named `<repo>-<version>`:

```console
$ python3 <deps.py> worktree \
    --lang <language> \
    --url <repo-url> \
    --version <version> \
    --tag <tag> \
    --registry-commit <commit>
```

Omit `--registry-commit` when step 5 returned none. The result's `tag_check` is `matches`, `differs`, or `unchecked`.

A matched branch, or the default branch after the user agrees, gives an unpinned worktree named `<repo>-<branch>-<sha7>`, so the directory never claims a version it is not. Use `--branch <branch>` for a matched branch and omit it for the default branch:

```console
$ python3 <deps.py> worktree \
    --lang <language> \
    --url <repo-url> \
    --version <version> \
    --branch <branch>
```

An existing worktree comes back as `skipped` with reason `worktree exists`, and its commit.

## 9. Report

Write it per `../../references/prose-rules.md`. Collect one result per dependency and let the script assemble the reply:

```console
$ python3 <deps.py> report --results - <<'EOF'
[{"package": "zod", "version": "3.23.8", "status": "pinned", "tag_check": "matches",
  "sha7": "1a2b3c4", "url": "https://github.com/colinhacks/zod",
  "path": "~/study/typescript/zod-3.23.8"}]
EOF
```

Fields: `package`, `version`, `status`, `branch` (unpinned), `reason` (skipped or failed), `tag_check`, `sha7`, `url`, `path`. `status` is one of `pinned`, `unpinned`, `skipped`, `failed`, and no other word. `path` is the `~/`-relative path the script printed. Leave out the `package` and `version` of a dependency the scan skipped for its name.

Reply with the `text` field, shaped per `../../references/reply-contract.md`. The study root appears as `~/study/`, the one local path the reply shows, per that contract's exception:

```text
✓ 2 worktrees ready

- zod@3.23.8 pinned 1a2b3c4 https://github.com/colinhacks/zod ~/study/typescript/zod-3.23.8
- vite@5.2.0 unpinned (release/5.2) 9f8e7d6 https://github.com/vitejs/vite ~/study/typescript/vite-release-5.2-9f8e7d6
```

The hero line is `✓ <n> worktrees ready`, or `⚠ <n> failed, <m> worktrees ready` when any dependency failed. `, tag differs` or `, tag unchecked` follows `pinned` when step 8 found it; after a `differs`, name the worktree commit and the registry commit. The commit makes the source citable at that revision, and a research run records it with `--ref <sha7>`. Suggest manual fixes only for failures, such as checking available tags.

A run halted before cloning prints the halted shape:

```text
⚠ Nothing was cloned: no interactive host to confirm the plan.

Rerun with the plan approved, or run the listed commands yourself.
```

A dependency with no usable repository:

```text
⚠ Nothing was cloned: left-pad has no usable repository.

- Give an https:// repository URL for it.
- Skip it.
```

Panel options: study another dependency, record the sources in a research run, stop.
