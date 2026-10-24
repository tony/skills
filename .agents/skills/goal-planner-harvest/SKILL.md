---
name: goal-planner-harvest
description: >-
  Use when mining prompt history for guardrails retyped into goals, to
  propose them as goal-planner profile entries.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--days <n>] [--min-count <n>] [--min-projects <n>]"
  source: "plugins/goal-planner/skills/harvest/SKILL.md"
---

# this skill

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

`<goal.py>` is `references/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command. Run each command by
itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call.

## Step 1: Export and count

Export prompt history per `references/history.md`, then count:

```console
$ python3 <goal.py> harvest \
    --history <export file> \
    --days 30
```

It prints `kept`, the sentences that clear the bar with their count, projects,
last use, hosts, and skill names; `set_aside`, the counts of recurring
sentences under the bar (`under_bar`) and of Codex-only ones (`codex_only`);
and `skipped_lines`, export lines that were not JSON. Codex prompts carry no
working directory, so a Codex-only guardrail cannot clear the project bar.
Report the export's coverage, skipped lines included, beside every count.

## Step 2: Sort what came back

For each sentence:

1. Match it to a module in `references/modules.md`. A match becomes
   that module's profile section, with the user's wording when it differs.
2. A sentence no module covers becomes a new profile section, named for what
   it guards.
3. Check every skill it names against this machine's catalog:

```console
$ python3 <goal.py> catalog
```

   A name that is gated or missing is proposed with the skill that replaces
   it, such as the `spike-ratchet` skill for `/spike:loop` or the `spike-bakeoff` skill.
4. Drop personal paths, remotes, and names from a sentence meant for a
   module's default; they belong in the profile's keys.

Read the profile (`$XDG_CONFIG_HOME/goal-planner/profile.md` or
`~/.config/goal-planner/profile.md`) and skip what it already says.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan lists each proposed profile change: the section, the new text, the
sentence it came from with its count, projects, and last use, and any skill
name it replaces. Wait for approval, then exit plan mode. Apply only the
approved changes to the profile, creating it from `templates/profile.md`
when it does not exist.

## Output

Write it per `references/prose-rules.md`. In this order:

1. Hero, one line: `✓ <n> guardrails proposed, <m> applied to the profile`.
2. `## Proposed`: each entry, its evidence, and whether it was applied.
3. `## Set aside`: sentences under the bar, Codex-only, or already present.
4. `## Coverage`: what the history export covered.
5. Ask with `ask-user-choice`: apply more, print a goal with the new profile,
   or stop. Without a question tool, print the options as a plain list and
   stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
