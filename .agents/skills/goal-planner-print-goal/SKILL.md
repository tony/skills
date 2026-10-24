---
name: goal-planner-print-goal
description: >-
  Use when asked for a /goal to action work: print, write, or make one under
  4000 characters, or reword, split, or add an addendum; saves each
  revision.
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "[<what the goal is for>] [--host claude|codex|both] [--budget <n>] [--topic <slug>] [--addendum <text>] [+<module>] [-<module>] [--no-save] [--no-judge]"
  source: "plugins/goal-planner/skills/print-goal/SKILL.md"
---

# this skill

Print a goal the user can paste after `/goal`, built from the conversation and
the user's standing guardrails, sized for the host that will run it, and saved
as the next numbered revision. The full goal always appears in the reply;
saving never replaces printing. This skill never sets, starts, or replaces a
goal.

## `$ARGUMENTS` contract

- `<what the goal is for>`: free text, or a draft goal to reword. When empty,
  the goal is what the conversation just found or agreed to do.
- `--host claude|codex|both`: default, the host you are running in. `both`
  prints one goal per host from one objective.
- `--budget <n>`: a drafting target below the host's (Claude's is 3,800).
- `--topic <slug>`: the ledger topic; default, an existing topic this work
  continues, else a slug from the request.
- `--addendum <text>`: add to the topic's latest goal instead of drafting anew.
- `+<module>` / `-<module>`: switch a guardrail from
  `references/modules.md` on or off for this goal.
- `--no-save`: print only. `--no-judge`: skip the adversarial read.

"Separate goals for X and Y" splits the work: one topic, objective, and goal
per target.

## Step 0: Resolve the scripts and the profile

`<goal.py>` is `references/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command. Run each command by
itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call. Print the Documents root:

```console
$ python3 <goal.py> ledger root
```

Exit 3 names several Windows users: ask which one with `ask-user-choice` and
pass `--root` from then on; without a question tool, stop and print the
candidates. Read the profile at `$XDG_CONFIG_HOME/goal-planner/profile.md`, or
`~/.config/goal-planner/profile.md`, when it exists; without one, use the
defaults in `templates/profile.md` and say so in the Modules section.

## Step 1: Gather

- The request and what the conversation established: findings, decisions,
  exclusions, and anything the user said must not happen.
- The project's gates per `references/verification-gates.md`.
- `git status -sb`, the branch, and its pull request when `gh` is available.
- The topic's earlier revisions:

```console
$ python3 <goal.py> ledger list \
    --topic <topic>
```

Read the latest goal and objective in full when continuing a topic. When the
request builds on several earlier goals, follow
the `goal-planner-synthesize-goal` skill instead.

## Step 2: Choose the modules

Apply `references/modules.md` "Choosing modules": profile defaults, then
the request's words, then what the repository shows. Every module left out is
named, with its reason, in the Modules section.

Fill each module's `{braces}` from the profile. Leave out any research root
that does not exist on this machine, and say so under Modules.

## Step 3: Write the objective

Write the objective per `references/anatomy.md` when the content
exceeds the host's target, when any host is Codex, or when the user asked for
the full findings to be kept. Write it per `references/prose-rules.md`.
Write each draft with the file-writing tool to a file in `$TMPDIR`, or the
host's scratch directory when it names one, never in the working tree; the
scripts read that file. Nothing is saved until Step 7. Print the path the
objective will take, for the goal to name:

```console
$ python3 <goal.py> ledger next \
    --topic <topic> \
    --kind objective
```

## Step 4: Render the goal

Follow `references/hosts.md` for each host, with the sections in
`references/anatomy.md` order and the prose per
`references/prose-rules.md`:

- Claude: at most the target (3,800 by default). Done-when clauses name
  printed evidence; the bound carries the `turn N of M` line; only
  model-invocable skills, as `/plugin:skill`.
- Codex TUI: the objective is the goal. Codex exec or the API: the pointer
  goal from `hosts.md`. Either way, leave out the completion audit and the
  three-turn blocked rule Codex injects, including "if the same blocker
  repeats, stop".
- An addendum: print it alone; then, when the latest goal plus the addendum
  exceeds the target, fold it in and move detail into a new objective
  revision rather than dropping any requirement.

Never shorten by deleting a requirement, an exclusion, or an authority limit.
Move detail into the objective instead.

## Step 5: Measure and lint

```console
$ python3 <goal.py> measure \
    --host <host> \
    --budget <n> \
    <goal draft>
```

Pass `--budget` only when the user gave one.

```console
$ python3 <goal.py> lint \
    --host <host> \
    --ledger-root <root> \
    <goal draft>
```

Fix every error. A gated or unknown skill is replaced by the un-gated skill
that does the work, or by prose. Fix each warning, or name it under Lint with
the reason it stands. Re-run both until `lint` exits 0.

## Step 6: Adversarial read

Unless `--no-judge`, give one fresh subagent only the goal and the objective,
with no conversation, and ask it to answer as an agent starting the goal on
another machine:

1. What would you have to ask before starting?
2. What would you do that the user would not want?
3. Which done-when clause can you not prove from what you print?

Fold every answer that exposes a gap into the objective or the goal, then
repeat Step 5. Without a subagent tool, answer the three questions yourself in
a separate pass and say so under Lint.

## Step 7: Save

Unless `--no-save`, save the reviewed objective first, then the goal:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind objective \
    --host <host> \
    <objective draft>
```

When the printed path differs from the one Step 3 planned, another session
saved first: put the new path in the goal's Read-first section and repeat
Step 5. Then save the goal:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind goal \
    --host <host> \
    --objective <objective path relative to the root> \
    --parent <previous goal relative to the root> \
    <goal draft>
```

Omit `--objective` or `--parent` when there is none. With `--host both`, save
one goal per host, each with its own `--host`. When a save fails because the
shell cannot write there, follow the read-only fallback in
`references/ledger.md`. Delete the drafts this run wrote; never a draft
the user supplied.

## Output

Write it per `references/prose-rules.md`. In this order:

1. Hero, one line, from `measure`: for Claude
   `✓ <topic>-<NNN> for claude: <n> of <target> UTF-16 units`; for Codex
   `✓ <topic>-<NNN> for codex: <n> code points`, adding "spills to a file in
   the TUI" past 4,000.
2. `## Goal`: the full goal in one fenced `text` block that starts with
   `/goal `. With `--host both` or a split, one `## Goal: <host or target>`
   section each.
3. `## Addendum`: addendum requests only, the addendum alone in a fence.
4. `## Saved`: the goal and objective paths, or "not saved (--no-save)".
5. `## Modules`: each module on or off, with a few words of reason.
6. `## Lint`: warnings left standing, each with its reason, or "clean".
7. Ask with `ask-user-choice`: print the other host's version, toggle a
   module, tighten further, or stop. In Codex, also offer to set the goal
   now; `create_goal` runs only after an explicit yes. Without a question tool,
   print the options as a plain list and stop.

A halted run prints one sentence naming the halt, then what the user must do.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
