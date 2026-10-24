# Ledger

Contents: Files, Numbering, Frontmatter, The Documents root, Commands (including saving from a read-only shell).

Every printed goal is saved; nothing saved stands in for printing it.

## Files

```text
<documents>/YYYY-MM-DD/goals/<topic>-NNN.md        the goal: what the user pastes
<documents>/YYYY-MM-DD/objectives/<topic>-NNN.md   the objective: the full statement
```

- `YYYY-MM-DD` is the local day of the save.
- `<topic>` is a kebab-case slug (`parser-fix`) that stays the same across
  revisions and days.
- The objective holds the full end state, keyed tasks, full module text,
  findings, and lineage (`anatomy.md`). Save one whenever the content exceeds
  the host's target or the goal is for Codex; a complete short goal needs none.

## Numbering

- `NNN` is three zero-padded digits per topic and kind, one past the highest
  number in any dated folder: a topic at `001` and `003` saves `004` next, and
  `002` is never refilled.
- Goals and objectives number independently. A reworded goal can point at the
  same objective; each goal's frontmatter names the objective revision it uses.
- A file is never overwritten. Two sessions saving the same topic at once get
  consecutive numbers.

## Frontmatter

In this order: `topic`, `kind`, `number`, `host`, `status`, then `objective`
and `parent` when set (paths relative to the Documents root), `utf16`,
`codepoints`, `created` (UTC). The body below it is exactly the text to paste.
Statuses: `draft` (printed), `set` (the user set it), `achieved`, `superseded`.

## The Documents root

First match wins:

1. `--root`.
2. `GOAL_PLANNER_ROOT`.
3. The profile's `documents:` (`auto` skips it).
4. On WSL, the Windows user's Documents folder: the one matching `$USER` or
   named in `$PATH`. Several candidates and no match is an error naming them.
5. `~/Documents`.

On WSL, a literal `~/Documents` names the Linux home's folder, not the Windows
one, so a goal always carries the resolved absolute path.

## Commands

`./goal.py` resolves from this file's own directory; write it as an
absolute path in each command. Print the resolved root and where it came from:

```console
$ python3 <goal.py> ledger root
```

Save a goal from a draft file and print its path, number, and size:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind goal \
    --host claude \
    --objective <YYYY-MM-DD>/objectives/<topic>-<NNN>.md \
    <draft file>
```

When the shell cannot write to the root (a read-only file system or a
sandboxed shell), print the path and the exact file text instead, then create
that path with the file-writing tool, using the printed `content` unchanged:

```console
$ python3 <goal.py> ledger save \
    --topic <topic> \
    --kind goal \
    --host claude \
    --dry-run \
    <draft file>
```

List a topic's saved goals and objectives:

```console
$ python3 <goal.py> ledger list \
    --topic <topic>
```

Gather earlier goals from the ledger, Codex, and a history export, newest
first, each with its full text:

```console
$ python3 <goal.py> find \
    --topic <topic> \
    --history <export file>
```
