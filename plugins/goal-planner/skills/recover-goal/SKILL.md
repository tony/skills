---
name: recover-goal
description: "Use when a goal from before is gone, or to print the current, previous, original, or latest goal again verbatim, from saved goals, history, or Codex."
argument-hint: "[current|previous|original|latest] [<words from the goal>] [--topic <slug>] [--with-history]"
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
---

# `/goal-planner:recover-goal`

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

`<goal.py>` is `../../scripts/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command. Run each command by
itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call.

## Step 1: Search

```console
$ python3 <goal.py> find \
    --kind goal \
    --topic <topic> \
    --text <words>
```

Drop `--topic` or `--text` when not given. This prints an index, newest
first: each hit's source, time, `ref`, size, and a preview, from the dated
`goals/` folders, Codex's goal database, and Codex's spill files that no goal
row points at any more. When nothing matches, or with `--with-history`, export
prompt history per `../../references/history.md` and repeat with
`--history <export file>`.

Inside Claude Code, a goal set in this session also appears in the
conversation as `Goal set: ...`; that text is a source too.

## Step 2: Choose the revision and print it

- `latest` and `current`: the newest hit. For `current`, prefer a Codex row
  whose status is `active`, or the newest `Goal set:` in this session.
- `previous`: the hit before the current one for the same topic or text.
- `original`: the oldest hit for the same topic or text. The index stops at
  20 hits per source; repeat Step 1 with `--limit 0` to list every one.

When two hits could be the one the user means, list them with their sources
and times and ask with `AskUserQuestion`; without a question tool, print both.

Print the chosen hit's text exactly, never retyped from the preview. `--ref`
searches every hit, past `--limit`, `--text`, and `--topic`, but only in the
sources named: keep `--history` when Step 1 used it, and leave it out
otherwise.

```console
$ python3 <goal.py> find \
    --kind goal \
    --history <export file> \
    --ref <ref>
```

A hit with an `error` reports a source that could not be read in full, such
as `skipped_lines` in a history export; say so beside the result. A Codex hit marked `missing` is a pointer whose spill file is gone: print the
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
    <file in $TMPDIR holding the verbatim text>
```

Use `--status draft` when the source shows only that it was printed.

When the save fails because the shell cannot write there, follow the
read-only fallback in `../../references/ledger.md`.

## Output

Write it per `../../references/prose-rules.md`. In this order:

1. Hero, one line: `✓ <topic> goal from <source>, <time>`.
2. `## Goal`: the text exactly as found, in one fenced `text` block.
3. `## Source`: where it came from (ledger path, Codex thread, or prompt time
   and agent), and whether its spill file was missing.
4. `## Saved`: the new ledger path, or "already in the ledger at <path>".
5. Ask with `AskUserQuestion`: print another revision, print it for the other
   host with `/goal-planner:print-goal`, or stop. Without a question tool,
   print the options as a plain list and stop.

A run that finds nothing prints one sentence naming every source searched and
the history coverage, then what the user can try: other words, a topic, or
`--with-history`.
