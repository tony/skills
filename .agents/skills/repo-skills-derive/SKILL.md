---
name: repo-skills-derive
description: >-
  Use when creating project-specific agent skills for a codebase or repo
  from its docs, git history, and transcripts, or setting up .agents/skills.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "[<repo path>] [--prefix <name>] [--since <date>] [--no-transcripts] [--no-shell-history] [--dry-run]"
  source: "plugins/repo-skills/skills/derive/SKILL.md"
---

# this skill

Write a repository's own skill set, generalist in shape and adept in
content: setup, architecture, style, gates, dependencies, review,
commits, checks, and whatever else its history shows agents relearning.
Evidence comes from the repository's files, git history, CI, AI
transcripts, and shell history. Each skill is tested with and without
itself before it lands, in two commits: the skills, then the
`.claude/skills` link.

`<evidence.py>` is `references/evidence.py`, resolved from this
skill's directory, not the repository root. Resolve it to an absolute
path once, print it, and use that literal path in every command. It
needs python 3.9 or newer. `<root>` is the target repository's top-level
directory, written literally in each command.

## `$ARGUMENTS` contract

- A positional path selects the target repository; empty means the
  current one.
- `--prefix <name>` names the skills `<name>-<area>`. Without it, propose
  a short prefix from the repository or package names in the plan.
- `--since <date>` bounds the git window; the default is `12 months ago`.
- `--no-transcripts` and `--no-shell-history` skip those sources.
- `--dry-run` runs Phase 1 in full, gates included, and stops after
  the plan.

Invoking this skill is the request to read AI transcripts and shell
history for this repository; nothing else is searched.

## Phase 0: Preconditions

Check these in order. A failure in step 1 or 2 halts the run; steps 3
and 4 only gather what later phases need.

1. `<root>` is a git repository and is neither the home directory nor a
   directory containing it.
2. No tracked file is modified. The two commits must hold only this
   run's work.
3. Read the repository's conventions files (`AGENTS.md`, `CLAUDE.md`,
   `GEMINI.md`, `.github/CONTRIBUTING.md`, any nested `AGENTS.md`) for
   its commit format, gates, and which file owns which rule.
4. Report the skills-link state; it decides commit 2:

   ```console
   $ python3 <evidence.py> --repo <root> link --check
   ```

   Exit 2 means `.claude/skills` holds real skill directories, foreign
   links, or a link elsewhere. Name them in the plan: a real skill
   directory moves into `.agents/skills` in commit 1 with the user's yes,
   and anything else is the user's to resolve before commit 2.

A halted run is one result sentence naming each blocker, such as the
modified files, then what the user must do about it: commit or stash
them, and run the skill again. No other sections.

## Phase 1: Gather evidence

Read-only. Follow `references/evidence-sources.md` for each
source: what to run, how to read it, and what never leaves the machine.
Write raw exports outside the working tree.

1. Norms and project files: the conventions files, manifests, task
   runners, CI workflows, tool configs, version pins, and generated
   files.
2. Gates: discover them per `references/verification-gates.md`,
   then run each local check once and record its exit code. A document's
   claim that a gate passes or fails is a claim to test, not a fact.
3. Git history:

   ```console
   $ python3 <evidence.py> --repo <root> git --since "<since>"
   ```

4. Every place the repository has lived:

   ```console
   $ python3 <evidence.py> --repo <root> paths
   ```

5. AI transcripts, unless `--no-transcripts`: one exhaustive search over
   every `cwd_globs` entry, then the summary filtered to this
   repository's directories.
6. Shell history, unless `--no-shell-history`, passing every checkout
   and every former location the transcript summary's `by_cwd` rows
   name:

   ```console
   $ python3 <evidence.py> --repo <root> shell \
       --path <checkout> \
       --path <earlier checkout>
   ```

7. Sibling repositories the prompts name as a source of changes, and
   upstream sources the prompts send agents to read.

## Phase 2: Choose the skill set

Read `references/skill-catalog.md`. Weigh each category against
the evidence, by sessions as well as commits: setup, pull requests and
reading docs leave few commits behind. A category skipped because "a
document covers it" needs that document checked first; a stale one is
a reason to write the skill.

Collect stale claims as you go: every place a conventions file
contradicts a measured fact. They become a report section, not edits.

## Phase 3: Orchestration plan

Enter plan mode before the first edit. In Claude Code call
`EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`.
Where plan mode is unavailable, present the plan as text.

Write the plan per `references/prose-rules.md`. It gives:

- The prefix and the branch. On the trunk, propose a topic branch named
  `<prefix>-skills`.
- Per skill: its name, its triggers, the evidence for it (counts,
  sessions, dates, files), and what it owns.
- Per skipped category: the evidence that did not clear the bar.
- Every path outside the repository a skill would name, each needing the
  user's yes.
- Each real skill directory under `.claude/skills`, to move into
  `.agents/skills`.
- The stale claims found, left for separate commits.
- Commit 1 (skills and the `AGENTS.md` pointer) and commit 2 (the link),
  with subjects in the repository's format.

Wait for approval, then exit plan mode. `--dry-run` stops here. Without
an interactive question tool (Codex, headless runs), print the plan and
stop.

On the trunk, create the approved branch before the first edit, so both
commits land on it:

```console
$ git -C <root> switch -c <prefix>-skills
```

## Phase 4: Watch each skill fail first

Before writing a skill, run its baseline per
`references/testing-skills.md`: one realistic task, a sub-agent
without the skill, a written record of what it got wrong. A category
whose baseline gets everything right needs no skill; drop it and say so.

## Phase 5: Write the skills

One directory per skill, `.agents/skills/<prefix>-<area>/SKILL.md`,
written per `references/prose-rules.md`. Each skill:

- Has frontmatter `name` matching its directory and a `description`
  starting `Use when`, listing triggers in the words a user types.
- Targets the failures its baseline showed, and nothing a baseline
  already got right.
- Points at the file that owns each rule instead of restating it. Where
  that file is stale, it states the measured fact and names the source
  of truth: a manifest, CI file, or config.
- Gives commands, paths and identifiers you have run, listed, or found
  in the tree during this run.
- Declares an output shape, including the shape of an empty result,
  when it reports (review, doc checks).
- Sets `disable-model-invocation: true` when it only makes sense asked
  for by name, such as setup.
- Carries no secret, no third party's name, and no transcript text
  beyond a few words of the user's own phrasing.

Add one paragraph to the repository's `AGENTS.md` (or `CLAUDE.md` when
that is the real file) naming `.agents/skills/` as the home of
step-by-step procedures that defer to the rule files, per
`references/prose-rules.md`. Name the folder, not the skills, so
the paragraph never goes stale.

## Phase 6: Watch each skill pass

Run the same task, word for word, with one added line pointing at the
skill. Fix each remaining miss and run again, at most three rounds per
skill. Report what still varies.

## Phase 7: Commit the skills

With the user's yes from the plan, move each real skill directory from
`.claude/skills` into `.agents/skills` first, so commit 2's link
replaces an empty directory:

```console
$ git -C <root> mv .claude/skills/<name> .agents/skills/<name>
```

Stage only the new and moved skill directories and the `AGENTS.md`
change, by path. Write the message in the repository's commit format, per
`references/prose-rules.md`: the why is the evidence (where agent
time goes, what the baselines got wrong), the what lists one line per
skill. No `Co-Authored-By` or tool trailer.

## Phase 8: Link `.claude/skills`

```console
$ python3 <evidence.py> --repo <root> link
```

It replaces per-skill links with one `.claude/skills` link to
`../.agents/skills`, and stages it past any gitignore. `changed: false`
means the link is already committed: skip commit 2 and say so in the
report. Otherwise confirm each `.claude/skills/*/SKILL.md` resolves, then
commit in the repository's format, per `references/prose-rules.md`:
the why is that a skill added to `.agents/skills` no longer needs its
own link. No `Co-Authored-By` or tool trailer.

Read back the commits this run made, two or one when commit 2 was
skipped, with `git log -<n> --format=%s` and
`git show --stat --format= HEAD~<n>..HEAD`. Never push.

## Output contract

Write the report per `references/prose-rules.md`.

1. Hero line, first line: `N skills on <branch>, M skipped`.
2. `## Skills`: one bullet per skill: its name, what it owns, and the
   baseline miss it fixed.
3. `## Skipped`: each category not written and why.
4. `## Stale claims`: each conventions-file claim the evidence
   contradicts, with the file and the source of truth. A claim in an
   always-loaded file leaks back through the skills; say which do.
5. `## Verification`: baseline and with-skill results per skill, the
   rounds taken, what still varies, and the link check.
6. End with an `ask-user-choice` panel: push the branch, fix the stale
   claims as separate commits, or stop. Without a question tool, print
   the options as a plain list and stop.

A `--dry-run` reply is the hero line `N skills planned, M skipped`, then
`## Plan`, `## Skipped` and `## Stale claims`, then the panel (run for
real, or stop). It edits and commits nothing.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold, and no local paths:

```text
2 skills on site-skills, 1 skipped

## Skills

- site-gates: the gate order, CI against local, and measuring a failure on the trunk; its baseline trusted a doc's list of failing gates.
- site-deps: the release cooldown, held packages, and bumps measured by unchanged output; its baseline bumped a release still inside the cooldown.

## Skipped

- unit guides: the repository has no guides tree and no session asked for one.

## Stale claims

- CONTRIBUTING.md says the dev server uses port 3003; the allocator in the server config takes 3040 to 3049. AGENTS.md repeats it, and two with-skill runs echoed it.

## Verification

- site-gates: the baseline missed the generated file a fresh checkout needs; with the skill it ran the generator first, in one round.
- site-deps: the baseline took a two-day-old release; with the skill it reported the release as gated, in two rounds.
- The link resolves every skill through `.claude/skills`.
```


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
