---
name: release-bump
description: >-
  Use when a user explicitly wants to bump a project to its next release,
  such as a new alpha, following its own scheme, then cut it.
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

Read the `release-cut` skill first: its Safety Contract applies unchanged, including
the `--push-tag` without `--tag` refusal, which applies now, before Phase 1.
`references/release_plan.py` resolves from this SKILL.md's directory; write
its absolute path literally in each command and never show it in replies.
Then read `references/release-conventions.md`. This skill writes no
prose of its own; `cut` writes the changelog and commit message.

---

## Phase 1: Discover the Current Position

Gather three signals and check they agree:

1. Manifest version, from the version-bearing files (conventions reference).
2. Latest tag, from the tag namespace of the manifest version. The script
   orders tags by parsed version, so a graduated prerelease never outranks its
   final; creation order and `git tag --sort` say nothing about version order.
   `namespaces` also names the prefix convention and the prerelease
   vocabulary the project has used (`pre_style`, `letters`).

   ```console
   $ python3 <absolute-release_plan.py> tags \
       --repo <repo> \
       --version <manifest-version>
   ```

3. CHANGES unreleased header: the version it already targets. A stable-track
   header like `## <project> 0.63.x (unreleased)` constrains the next release
   to the `0.63` series unless the user overrides; a prerelease-track header
   names the next version outright.

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

The script classifies the scheme and builds the candidates as concrete
versions, not bump names. Pass the tag prefix from Phase 1 so it reads the
project's prerelease vocabulary from its tags.

```console
$ python3 <absolute-release_plan.py> candidates \
    --repo <repo> \
    --prefix <tag-prefix> \
    --current <manifest-version>
```

With current `0.1.9a1` on a prerelease track it returns the next prerelease
`0.1.9a2` (the routine increment) and graduation to final `0.1.9`, plus
segment promotion (`a` to `b` to `rc`) only if the tag history uses those
segments. With current `0.1.9` on a stable track it returns patch `0.1.10`,
minor `0.2.0`, major `1.0.0`, and a new prerelease series in the project's
vocabulary (`0.2.0a0`, or `0.2.0-next.0` on npm; the scheme rules are cited under Sources
in the conventions reference). Offer `post`/`dev` releases
only when the user asks or the argument names one. A refusal (a `.post`
or `.dev` current version, a non-`MAJOR.MINOR.PATCH` stable version) means
asking the user for the version.

## Phase 3: Resolve the Version

- Explicit version argument (e.g. `0.2.0a0`): it must sort after the current
  version under the project's scheme, which the script reads from the tag
  history. A refusal stops the run with its reason; a `-next.N` version in a
  PEP 440 project is one.

  ```console
  $ python3 <absolute-release_plan.py> compare <manifest-version> <version> \
      --repo <repo> \
      --prefix <tag-prefix>
  ```

- Bump-type argument (`patch`, `minor`, `major`, `prerelease`, `final`): rerun
  `candidates` with `--kind <type>`. When the result has `"ambiguous": true`
  (`prerelease` on a stable track could mean `0.1.10a0` or `0.2.0a0`),
  present the interpretations via `ask-user-choice`; without it (Codex,
  headless runs), list them and stop.
- No argument: present the Phase 2 candidates via `ask-user-choice`,
  recommending the increment the project performed most recently. Label each
  option with the concrete version and when it is the right choice. Without
  `ask-user-choice`, list the candidates and stop.

Never proceed on an inferred version. The user picks, and the selection
confirms the version only; the Safety Contract in the `release-cut` skill decides
what the flags authorize.

## Phase 4: Cut

Run the complete the `release-cut` skill procedure (the `release-cut` skill, Phase 1
onward) with the chosen version, forwarding any `--push` / `--tag` /
`--push-tag` flags the user passed. `cut`'s Orchestration Plan applies; choosing
a version does not replace it. Graduating to a final makes the run a
graduation: `cut` writes the final's section from the net change since the
previous final (`references/graduation.md`).

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
