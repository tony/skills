---
name: goal-planner-setup
description: >-
  Use when setting up goal-planner on a machine: create or link the profile,
  and resolve its Documents root and research paths.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--from <synced profile path>]"
  source: "plugins/goal-planner/skills/setup/SKILL.md"
---

# this skill

Give this machine a goal-planner profile: copy the template or link a profile
the user syncs across machines, then fill in what only this machine knows.
Invoked by name, never routed to on the model's initiative: it writes the
user's configuration.

## `$ARGUMENTS` contract

- `--from <path>`: a profile kept in a synced folder, dotfiles, or a private
  repository. It is linked, not copied, so every machine reads one file.

## Step 0: Resolve the script

`<goal.py>` is `references/goal.py`, resolved from this skill's own
directory; write it as an absolute path in every command.

## Step 1: Find what exists

- The profile path: `$XDG_CONFIG_HOME/goal-planner/profile.md`, or
  `~/.config/goal-planner/profile.md`. Read it when it exists.
- The Documents root and where it came from:

```console
$ python3 <goal.py> ledger root
```

  On WSL with several Windows users, ask which is the user's with
  `ask-user-choice` and record it as `documents:`.
- Each `research_roots` entry: keep those that exist here and name the rest.
- The optional tools: `uvx` with the agentgrep pin from
  `references/history.md`, and `gh`.

## Step 2: Propose and write

Show the profile as it would be written: the template from
`templates/profile.md` or the `--from` file, with this machine's
`documents:` and the research roots that exist. Ask with `ask-user-choice`
before writing; without a question tool, print it and stop.

With approval, write the profile, or create the link to `--from`. Never
overwrite an existing profile: show the difference and ask instead.

## Output

Write it per `references/prose-rules.md`. In this order:

1. Hero, one line: `✓ profile at <path>, Documents root <root> (<source>)`.
2. `## Machine`: the Documents root, research roots found and missing, and
   the optional tools found.
3. `## Profile`: written, linked, or unchanged, and the path.
4. Ask with `ask-user-choice`: run the `goal-planner-harvest` skill to fill the
   profile from history, print a goal, or stop. Without a question tool,
   print the options as a plain list and stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
