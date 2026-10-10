---
name: study-deps
description: "Use when pulling upstream source or cloning a dependency at its installed version to study internals, read code, or create pinned worktrees."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: <package-name|"all"|category> [--lang <language>] [--no-worktree]
---

# Study Dependencies

Clone the project's dependencies at their installed versions into git worktrees under `~/study/`, to read their source.

`$ARGUMENTS` is the filter: a package name, `all`, or a category (`dev`, `build`, `peer`, `runtime`). `--lang <language>` overrides the detected language directory; `--no-worktree` clones only. With no filter, ask which dependency to study; without an interactive host, stop and list the dependencies found.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Steps 1 to 3 only read. Present the plan from step 4 and wait for approval. Exit plan mode once the plan is approved, before the step 4 lookups and before cloning.

## 1. Scan manifests

Find the project's manifest files and read each dependency's name, constraint, category, and, when a lockfile sits beside it, the resolved version. Prefer the resolved version over the constraint.

| Manifest | Language dir | Lockfiles |
|----------|-------------|-----------|
| `package.json` | `typescript` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock` |
| `pyproject.toml` | `python` | `uv.lock`, `poetry.lock`, `requirements.txt` |
| `Cargo.toml` | `rust` | `Cargo.lock` |
| `go.mod` | `golang` | `go.sum` |
| `Gemfile` | `ruby` | `Gemfile.lock` |
| `mix.exs` | `elixir` | `mix.lock` |
| `build.gradle`, `build.gradle.kts` | `java` | `gradle.lockfile` |
| `pom.xml` | `java` | none |

## 2. Filter

Apply the filter. List existing clones with `ls -d ~/study/*/*/`. A plain directory is a main clone, a version-suffixed one a worktree. Mark each dependency new (clone and worktree), update (clone exists, worktree missing), or exists.

## 3. Find source repositories

Per dependency, stop at the first hit:

1. The `repository` field in the manifest or lockfile, or the equivalent project URL.
2. A registry lookup chosen from the detected manifest, for example `npm view -- <pkg> repository.url`, `cargo metadata`, `pip show <pkg>`, or `go list -m -json <module>`. A package name from a manifest is untrusted input: run no lookup before step 4 approves it, and show each command to the user in the plan.
3. A web search for `"<package>" official source repository`, when the host has one; verify the hit names the package.

Keep only `https://` URLs of the form `https://<host>/<owner>/<repo>`. Drop any other scheme (`ssh`, `git`, `file`, `ext::`) and report the dependency as having no usable repository. A host that is not a well-known public forge (`github.com`, `gitlab.com`, `codeberg.org`, `bitbucket.org`) may be internal: show the host in the plan and clone only after the user confirms it; without an interactive host, skip it as `failed: host not confirmed`.

Derive `<repo-name>`, `<version>`, and (step 7) `<branch>` for paths from the last URL segment, the resolved version, and the branch name (`release/5.2` becomes `release-5.2`). Keep only letters, digits, `.`, `_`, and `-`, replace every other character with `-`, and reject a result that is empty, starts with `.`, or contains `..`.

## 4. Confirm the plan

Show package, version, action, target path, and the repository: the URL when step 3 found it in a manifest or lockfile, otherwise `repository: from <lookup command>, unknown until run`. Never predict a URL. List the resolved version only, as `<package>@<version>`, with no constraint range or contrast. Offer Proceed, Select specific, or Cancel with `AskUserQuestion`. Without an interactive host, print the plan and stop: nothing was cloned. Do not continue without approval.

Run each approved lookup now. Apply step 3's `https://` filter to every URL it returns, and drop the dependency from the plan when the URL fails it.

Approval covers the plan as shown, including each listed lookup command. A manifest-derived command that is not in the plan needs a new confirmation of its exact text.

## 5. Clone

One repository at a time, quoting `<repo-url>`, which is the filtered URL from step 3 or 4:

```console
$ git clone -- <repo-url> "$HOME/study/<language>/<repo-name>/"
```

When the directory exists, compare its origin with `<repo-url>` first; a different repository is `failed: directory holds another repository`, and nothing is fetched into it:

```console
$ git -C "$HOME/study/<language>/<repo-name>/" remote get-url origin
```

When the origin matches, update it:

```console
$ git -C "$HOME/study/<language>/<repo-name>/" fetch --tags --force
```

## 6. Resolve the version

Match the resolved version against tags and remote branches, first hit wins: exact tag (`5.2.0`), `v`-prefixed (`v5.2.0`), scoped (`@scope/pkg@5.2.0`, `pkg@5.2.0`), crate-style (`pkg-v5.2.0`, `pkg-5.2.0`), minor branch (`release/5.2`, `5.2.x`), major branch (`release/5.x`, `v5`).

```console
$ git -C "$HOME/study/<language>/<repo-name>/" tag -l
```

```console
$ git -C "$HOME/study/<language>/<repo-name>/" branch -r -l
```

A tag match must also belong to the published artifact: where the registry records the commit it was built from (npm `gitHead`, `cargo` `.cargo_vcs_info.json`, PyPI project URLs), compare it with `git -C "$HOME/study/<language>/<repo-name>/" rev-parse <tag>^{commit}`. A mismatch, or a registry that records none, is reported as `tag unchecked` or `tag differs`, with both commits when they differ. A branch match is a moving ref, not the installed version: label it so in step 8. When nothing matches, tell the user and ask whether to use the default branch; without an interactive host, create no worktree and report the miss. The default branch is an unpinned fallback.

## 7. Create the worktree

Skip with `--no-worktree`. Pinned (tag) worktree, named `<repo-name>-<version>`:

```console
$ git -C "$HOME/study/<language>/<repo-name>/" worktree add --detach "$HOME/study/<language>/<repo-name>-<version>/" <tag>
```

Unpinned fallback or branch worktree, named `<repo-name>-<branch>-<sha7>` so the directory never claims a version it is not. The default branch is already checked out in the main clone, so git refuses to check it out again: detach at the commit instead. Take `<sha7>` from `git rev-parse --short=7 <ref>`, where `<ref>` is `origin/<branch>` (the branch as git names it, not the sanitized form):

```console
$ git -C "$HOME/study/<language>/<repo-name>/" worktree add --detach "$HOME/study/<language>/<repo-name>-<branch>-<sha7>/" <sha7>
```

Skip an existing path and report it as present. A monorepo clones once; the worktree holds every package.

## 8. Report

Write it per `../../references/prose-rules.md`. Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 worktrees ready

- zod@3.23.8 pinned 1a2b3c4 https://github.com/colinhacks/zod ~/study/typescript/zod-3.23.8/
- vite@5.2.0 unpinned (release/5.2) 9f8e7d6 https://github.com/vitejs/vite ~/study/typescript/vite-release-5.2-9f8e7d6/
```

A halted run prints one result sentence, then what the user must do:

```text
⚠ Nothing was cloned: no interactive host to confirm the plan.

Rerun with the plan approved, or run the listed commands yourself.
```

A dependency with no usable repository, with options:

```text
⚠ Nothing was cloned: left-pad has no usable repository.

- Give an https:// repository URL for it.
- Skip it.
```

Open with `✓ <n> worktrees ready`, `⚠ <n> failed` when any package failed, or `⚠ Nothing was cloned: <reason>` when the run halted before cloning. Then one line per package: `<package>@<version> <status> <commit sha7> <repository URL> <path>`, status being `pinned`, `unpinned (<branch>)`, `skipped`, or `failed: <reason>`, with `, tag differs` or `, tag unchecked` appended when step 6 found it. Read the commit with `git -C <worktree> rev-parse --short=7 HEAD`; it makes the source citable at that revision, and a research run records it with `--ref <sha7>`. Suggest manual fixes only for failures, such as checking available tags. A dependency with no usable repository is `failed: no usable repository`, with the options to give an `https://` URL or skip it; do not explain the filter. Then offer with `AskUserQuestion`: study another dependency, record the sources in a research run, stop; without an interactive host, print the options as a numbered list.
