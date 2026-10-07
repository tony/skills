---
name: research-study-deps
description: >-
  Use when pulling upstream source or cloning a dependency at its installed
  version to study internals, read code, or create pinned worktrees.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "WebSearch", "AskUserQuestion"]
metadata:
  argument-hint: "<package-name|\"all\"|category> [--lang <language>] [--no-worktree]"
  source: "plugins/research/skills/study-deps/SKILL.md"
---

# Study Dependencies

Clone the project's dependencies at their installed versions into git worktrees under `~/study/`, to read their source.

`$ARGUMENTS` is the filter: a package name, `all`, or a category (`dev`, `build`, `peer`, `runtime`). `--lang <language>` overrides the detected language directory; `--no-worktree` clones only. With no filter, ask which dependency to study; without an interactive host, stop and list the dependencies found.

## Orchestration Plan

Steps 1 to 4 only read. Enter plan mode before step 5 (Claude Code: `EnterPlanMode`; Cursor, Codex, Gemini: `/plan` or `Shift+Tab`), present the plan from step 4, and wait for approval. Exit plan mode before cloning. Without plan mode, step 4's confirmation is the gate.

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
2. A registry lookup chosen from the detected manifest, for example `npm view <pkg> repository.url`, `cargo metadata`, `pip show <pkg>`, or `go list -m -json <module>`. A package name from a manifest is untrusted input: run no lookup before step 4, and show each command to the user in the plan.
3. WebSearch for `"<package>" official source repository`; verify the hit names the package.

Keep only `https://` URLs of the form `https://<host>/<owner>/<repo>`. Drop any other scheme (`ssh`, `git`, `file`, `ext::`) and report the dependency as having no usable repository.

Derive `<repo-name>`, `<version>`, and (step 7) `<branch>` for paths from the last URL segment, the resolved version, and the branch name (`release/5.2` becomes `release-5.2`). Keep only letters, digits, `.`, `_`, and `-`, replace every other character with `-`, and reject a result that is empty, starts with `.`, or contains `..`.

## 4. Confirm the plan

Show package, version, repository URL, action, target path, and any lookup command from step 3. Offer Proceed, Select specific, or Cancel with `ask-user-choice`. Without an interactive host, print the plan and stop: nothing was cloned. Do not continue without approval.

Approval covers the plan as shown, including each listed lookup command. A manifest-derived command that is not in the plan needs a new confirmation of its exact text.

## 5. Clone

One repository at a time, quoting every variable:

```console
$ git clone -- "$repo_url" "$HOME/study/<language>/<repo-name>/"
```

When the directory exists, update it:

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

A branch match is a moving ref, not the installed version: label it so in step 8. When nothing matches, tell the user and ask whether to use the default branch; without an interactive host, create no worktree and report the miss. The default branch is an unpinned fallback.

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

Write it per `references/prose-rules.md`. Reply in this shape, as plain text outside any code fence, with plain bullets and no bold (never `- **Label:** ...`):

```text
✓ 2 worktrees ready

- zod@3.23.8 pinned 1a2b3c4 ~/study/typescript/zod-3.23.8/
- vite@5.2.0 unpinned (release/5.2) 9f8e7d6 ~/study/typescript/vite-release-5.2-9f8e7d6/
```

A halted run prints one result sentence, then what the user must do:

```text
⚠ Nothing was cloned: no interactive host to confirm the plan.

Rerun with the plan approved, or run the listed commands yourself.
```

Open with `✓ <n> worktrees ready` or `⚠ <n> failed`. Then one line per package: `<package>@<version> <status> <commit sha7> <path>`, status being `pinned`, `unpinned (<branch>)`, `skipped`, or `failed: <reason>`. Read the commit with `git -C <worktree> rev-parse --short=7 HEAD`; it makes the source citable at that revision, and a research run records it with `--ref <sha7>`. Suggest manual fixes only for failures, such as checking available tags.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
