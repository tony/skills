---
name: goal-planner-synthesize-goal
description: >-
  Use when making a new goal based on earlier or prior goals, synthesizing
  the current goal with a plan, or updating a goal after progress.
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "Agent", "AskUserQuestion"]
metadata:
  argument-hint: "[<what changed or what the new goal adds>] [--topic <slug>] [--host claude|codex|both] [--with-history]"
  source: "plugins/goal-planner/skills/synthesize-goal/SKILL.md"
---

# this skill

Build the next goal from the earlier ones: read each in full, decide what
every earlier task or group becomes, check that against the current state,
and print the new goal with its lineage. Nothing an earlier goal required
disappears without a recorded reason.

## `$ARGUMENTS` contract

- `<what changed>`: the plan, findings, or steering the new goal adds. When
  empty, the conversation since the last goal.
- `--topic <slug>`: the ledger topic; default, the one this work continues.
- `--host`: as in the `goal-planner-print-goal` skill.
- `--with-history`: also read earlier goals from local prompt history.

## Step 0: Resolve the script

`<goal.py>` is `references/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command. Run each command by
itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call. Resolve the root and profile
as in Step 0 of the `goal-planner-print-goal` skill.

## Step 1: Gather the lineage

```console
$ python3 <goal.py> ledger list \
    --topic <topic>
```

```console
$ python3 <goal.py> find \
    --topic <topic>
```

With `--with-history`, or when the ledger holds no earlier goal, export
prompt history per `references/history.md` and add
`--history <export file>`. Read every earlier goal and objective in full.

## Step 2: Map and reconcile

Follow `references/lineage.md`: decide kept, changed, done, or dropped
for each earlier item with its key, check every "done" against the tree, the
pull request, and CI as they are now, and carry explicit holds forward. Ask
with `ask-user-choice` before dropping anything the user did not drop in this
conversation; without a question tool, keep it.

## Step 3: Write the objective

Write it per `references/anatomy.md` and
`references/prose-rules.md`, opening with the `## Lineage` table from
`lineage.md`. Save it:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind objective \
    --host <host> \
    --parent <previous objective relative to the root> \
    <objective draft>
```

When the save fails because the shell cannot write there, follow the
read-only fallback in `references/ledger.md`.

## Step 4: Render, check, and save the goal

Follow Steps 2 and 4 through 7 of the `goal-planner-print-goal` skill with this objective,
passing the topic's latest goal as `--parent`.

## Output

Write it per `references/prose-rules.md`. In this order:

1. Hero, one line: `✓ <topic>-<NNN> for <host>: <n> of <target> characters,
   <k> earlier items carried`.
2. `## Goal`: the full goal in one fenced `text` block starting with `/goal `.
3. `## Lineage`: one line per earlier item: key, decision, and reason.
4. `## Saved`: the goal and objective paths.
5. `## Modules`: each module on or off, with its reason.
6. `## Lint`: warnings left standing, or "clean".
7. Ask with `ask-user-choice`: print the other host's version, revisit a
   dropped item, or stop. Without a question tool, print the options as a
   plain list and stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
