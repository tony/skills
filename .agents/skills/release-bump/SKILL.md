---
name: release-bump
description: >-
  Use when discovering and confirming the next version from a project's own
  release scheme before cutting the release.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[patch|minor|major|prerelease|final|<version>] [--push] [--tag] [--push-tag]"
  source: "plugins/release/skills/bump/SKILL.md"
---

# Bump to the Next Version

Discover the project's current version and scheme, work out what "next"
means, get the user's explicit choice, then run the full the `release-cut` skill
procedure at that version.

Arguments: $ARGUMENTS

If `--push-tag` is present without `--tag`, refuse now, before Phase 1:
reply that `--push-tag` needs `--tag` in the same run and stop. Then read
`references/release-conventions.md`. The safety contract in
the `release-cut` skill applies unchanged. This skill writes no
prose of its own; `cut` writes the changelog and commit message.

---

## Phase 1: Discover the Current Position

Gather three signals and check they agree:

1. **Manifest version**: from the version-bearing files (conventions
   reference).
2. **Latest tag**: `git tag --list --sort=-version:refname` within the
   namespace of the manifest version (its prefix, such as `v` or `pkg@`),
   noting the prefix convention and the increment vocabulary the project
   has used (aN, bN, rcN, postN, devN, `-next.N`, plain semver). Creation
   order says nothing about version order.
3. **CHANGES unreleased header**: the version it already targets. A
   stable-track header like `## <project> 0.63.x (unreleased)` constrains
   the next release to the `0.63` series unless the user overrides; a
   prerelease-track header names the next version outright.

If the signals disagree (manifest ahead of tags, CHANGES targeting a
different series), surface the discrepancy before proposing anything. When
the repo holds several version-bearing packages or tag namespaces and the
arguments do not name one, ask which release track this is; without a
question tool, list the tracks and stop.

If the current version cannot be established (no manifest version, no tags,
no changelog), stop. Name the three signals, say which are absent, and
propose no version, bump type, or example. Ask the user for the current
version or the project root.

## Phase 2: Enumerate Candidates

Classify the scheme per the conventions reference and build the candidates
as concrete versions, not bump names. With current `0.1.9a1` on a
prerelease track: next prerelease `0.1.9a2` (the routine increment),
graduate to final `0.1.9`, and segment promotion (`a` → `b` → `rc`) only if
the tag history uses those segments. With current `0.1.9` on a stable
track: patch `0.1.10`, minor `0.2.0`, major `1.0.0`, or a new prerelease
series (`0.2.0a0`, or `0.2.0-next.0` on npm) in the project's vocabulary.
Offer `post`/`dev` releases only when the user asks or the argument names
one.

## Phase 3: Resolve the Version

- **Explicit version argument** (e.g. `0.2.0a0`): validate it sorts after
  the current version and fits the scheme, then proceed. Order versions with
  the project's own parser or version tool when it has one; otherwise apply the
  conventions reference's scheme rules and show the comparison. If it breaks the
  scheme (a `-next.N` version in a PEP 440 project), stop and ask.
- **Bump-type argument** (`patch`, `minor`, `major`, `prerelease`, `final`):
  map it to the concrete candidate. If the mapping is ambiguous
  (`prerelease` on a stable track could mean `0.1.10a0` or `0.2.0a0`),
  present the interpretations via `ask-user-choice`; without it (Codex,
  headless runs), list them and stop.
- **No argument**: present the Phase 2 candidates via `ask-user-choice`,
  recommending the increment the project performed most recently. Label each
  option with the concrete version and when it is the right choice. Without
  `ask-user-choice`, list the candidates and stop.

Never proceed on an inferred version. The user picks; the panel
selection confirms the version only. It never authorizes a tag or a
push; only the literal flags do.

## Phase 4: Cut

Run the complete the `release-cut` skill procedure (the `release-cut` skill, Phase 1
onward) with the chosen version, forwarding any `--push` / `--tag` /
`--push-tag` flags the user passed. The flag check at the top of this skill already ran.

## Output

Never name local or temp paths. A completed run ends with `cut`'s
output. A stopped run (missing signals, unresolved version, refused
flag) is one result sentence, then what the user needs to do. The
sentence carries no parenthetical about the repo or environment and no
clause explaining why.

Reply to a stop in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
No version bumped: this project has no manifest version, git tag, or changelog unreleased header.

- Tell me the current version, or
- Run release-cut <version> with the version you want.
```


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
