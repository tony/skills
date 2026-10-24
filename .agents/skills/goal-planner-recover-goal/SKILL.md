---
name: goal-planner-recover-goal
description: >-
  Use when a goal from before is gone, or to print the current, previous,
  original, or latest goal again verbatim, from saved goals, history, or
  Codex.
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[current|previous|original|latest] [<words from the goal>] [--topic <slug>] [--with-history]"
  source: "plugins/goal-planner/skills/recover-goal/SKILL.md"
---

# this skill

Find a goal the user set or printed before and print it again, verbatim, with
where it came from. Nothing is paraphrased, shortened, or merged.

## `$ARGUMENTS` contract

- `current`, `previous`, `original`, or `latest`: which revision. Default:
  `latest`.
- `<words from the goal>`: text the goal contains, matched without case.
- `--topic <slug>`: limit saved goals to one topic.
- `--with-history`: also search local prompt history. It is on whenever the
  ledger and Codex have nothing.

## Step 0: Resolve the script

`<goal.py>` is `references/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command.

## Step 1: Search

```console
$ python3 <goal.py> find \
    --topic <topic> \
    --text <words>
```

Drop `--topic` or `--text` when not given. This reads the dated `goals/`
folders, Codex's goal database, and Codex's spilled `goal-objective.md`
files. When nothing matches, or with `--with-history`, export prompt history
per `references/history.md` and repeat with `--history <export file>`.

Inside Claude Code, a goal set in this session also appears in the
conversation as `Goal set: ...`; that text is a source too.

## Step 2: Choose the revision

- `latest` and `current`: the newest hit. For `current`, prefer a Codex row
  whose status is `active`, or the newest `Goal set:` in this session.
- `previous`: the hit before the current one for the same topic or text.
- `original`: the oldest hit for the same topic or text.

When two hits could be the one the user means, list them with their sources
and times and ask with `ask-user-choice`; without a question tool, print both.

A Codex hit marked `missing` is a pointer whose spill file is gone: print the
pointer and say the full text is not on this machine.

## Step 3: Save it when the ledger lacks it

A hit from Codex or prompt history that the ledger does not hold is saved as
the topic's next goal revision, so the next search finds it:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind goal \
    --host <host the source shows> \
    --status set \
    <file holding the verbatim text>
```

Use `--status draft` when the source shows only that it was printed.

## Output

Write it per `references/prose-rules.md`. In this order:

1. Hero, one line: `✓ <topic> goal from <source>, <time>`.
2. `## Goal`: the text exactly as found, in one fenced `text` block.
3. `## Source`: where it came from (ledger path, Codex thread, or prompt time
   and agent), and whether its spill file was missing.
4. `## Saved`: the new ledger path, or "already in the ledger at <path>".
5. Ask with `ask-user-choice`: print another revision, print it for the other
   host with the `goal-planner-print-goal` skill, or stop. Without a question tool,
   print the options as a plain list and stop.

A run that finds nothing prints one sentence naming every source searched and
the history coverage, then what the user can try: other words, a topic, or
`--with-history`.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
