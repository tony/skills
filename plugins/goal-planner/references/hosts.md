# Hosts

Contents: Limits and counting, Who judges completion, Rendering for Claude Code, Rendering for Codex, Naming skills in a goal, Checking a goal.

What Claude Code and Codex do with a goal, and what each rendering must
therefore contain. Measured against Claude Code 2.1.310 and Codex 0.164.0.

## Limits and counting

- Claude Code accepts a `/goal` condition of at most 4,000 characters,
  counted as JavaScript string length: UTF-16 code units, so an emoji or other
  astral character counts twice. Longer text is refused with "Goal condition
  is limited to 4000 characters".
- The planner's Claude target is 3,800, which leaves 200 characters for an
  addendum the user types before setting the goal.
- Codex stores an objective of at most 4,000 code points. Its TUI writes a
  longer objective to `$CODEX_HOME/attachments/<uuid>/goal-objective.md` and
  stores a pointer to it. `codex exec` has no `/goal` command and answers one
  as a plain prompt; the goal API and the model's goal tool reject an
  objective over the cap.

## Who judges completion

- Claude Code: after every turn, a separate small model reads the condition
  and the conversation. It runs no commands and reads no files, so whatever it
  must judge has to be printed in the conversation.
- Codex: the working agent marks its own goal complete. Every continuation
  turn Codex injects a completion audit (treat completion as unproven, check
  every requirement against current state, never narrow the objective) and a
  rule to mark a goal blocked only after the same blocker repeats for three
  goal turns.

## Rendering for Claude Code

- At most 3,800 UTF-16 units, the sections in `anatomy.md` order.
- The objective is named as required context for the worker; nothing the
  evaluator must judge lives only there.
- Done-when clauses name printed evidence, and the bound comes with the line
  `turn N of M`.
- Only skills the model can invoke, in `/plugin:skill` form.

## Rendering for Codex

- In the TUI, the objective itself is the goal; the TUI handles its size.
- For `codex exec`, the IDE, or the API, a pointer goal under 4,000 code
  points: `Read the objective at <absolute path> before continuing.`, then the
  end state and the done-when clause.
- Leave out the audit and blocked rules Codex already injects.
- Skills in `$plugin:skill` form. Never set a token budget unless the user
  asks for one.

## Naming skills in a goal

A skill with `disable-model-invocation: true` cannot be invoked by the model.
In a non-interactive test, a goal naming one was refused on its first turn, so
naming it in the goal grants nothing. Name the un-gated skill that runs it
instead: `/spike:ratchet` runs probes and bakeoffs itself, so a goal never
needs `/spike:probe` or `/spike:bakeoff`. A skill that was renamed or removed
fails the same way, only later.

## Checking a goal

`../scripts/goal.py` resolves from this file's own directory; write it as an
absolute path in each command. Measure a draft:

```console
$ python3 <goal.py> measure \
    --host claude \
    <draft file>
```

Lint it against this machine's installed skills and the ledger root:

```console
$ python3 <goal.py> lint \
    --host claude \
    --ledger-root <documents> \
    <draft file>
```

`measure` exits 1 past the cap, and for Codex with `--no-spill` (exec and the
API). `lint` exits 1 on any error and lists warnings for the bound, missing
evidence, home paths, module placeholders left unfilled, and the drafting
target: Claude's 3,800, or `--budget` on either command.
