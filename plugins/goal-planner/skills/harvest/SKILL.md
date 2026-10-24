---
name: harvest
description: "Use when mining prompt history for guardrails retyped into goals, to propose them as goal-planner profile entries."
argument-hint: "[--days <n>] [--min-count <n>] [--min-projects <n>]"
allowed-tools: ["Bash", "Read", "Edit", "Write", "AskUserQuestion"]
disable-model-invocation: true
---

# `/goal-planner:harvest`

Find the guardrail sentences the user keeps retyping into goals and propose
each as a profile entry, so future goals carry it without the typing. It
edits only the profile, and only what the user approves. Invoked by name,
never routed to on the model's initiative: it rewrites the user's defaults.

## `$ARGUMENTS` contract

- `--days <n>`: how recent the latest use must be; default 30.
- `--min-count <n>` and `--min-projects <n>`: the evidence bar; default 5
  prompts across 2 projects, the bar `self-improvement:sweep` uses for a
  retyped procedure.

## Step 0: Resolve the script

`<goal.py>` is `../../scripts/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command. Run each command by
itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call.

## Step 1: Export and count

Export prompt history per `../../references/history.md`, then count:

```console
$ python3 <goal.py> harvest \
    --history <export file> \
    --days 30
```

Report the export's coverage beside every count. Codex prompts carry no
working directory, so a guardrail typed only in Codex cannot clear the project
bar; say how many Codex-only sentences were set aside.

## Step 2: Sort what came back

For each sentence:

1. Match it to a module in `../../references/modules.md`. A match becomes
   that module's profile section, with the user's wording when it differs.
2. A sentence no module covers becomes a new profile section, named for what
   it guards.
3. Check every skill it names against this machine's catalog:

```console
$ python3 <goal.py> catalog
```

   A name that is gated or missing is proposed with the skill that replaces
   it, such as `/spike:ratchet` for `/spike:loop` or `/spike:bakeoff`.
4. Drop personal paths, remotes, and names from a sentence meant for a
   module's default; they belong in the profile's keys.

Read the profile (`$XDG_CONFIG_HOME/goal-planner/profile.md` or
`~/.config/goal-planner/profile.md`) and skip what it already says.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan lists each proposed profile change: the section, the new text, the
sentence it came from with its count, projects, and last use, and any skill
name it replaces. Wait for approval, then exit plan mode. Apply only the
approved changes to the profile, creating it from `../../templates/profile.md`
when it does not exist.

## Output

Write it per `../../references/prose-rules.md`. In this order:

1. Hero, one line: `✓ <n> guardrails proposed, <m> applied to the profile`.
2. `## Proposed`: each entry, its evidence, and whether it was applied.
3. `## Set aside`: sentences under the bar, Codex-only, or already present.
4. `## Coverage`: what the history export covered.
5. Ask with `AskUserQuestion`: apply more, print a goal with the new profile,
   or stop. Without a question tool, print the options as a plain list and
   stop.
