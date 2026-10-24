# goal-planner

Print, synthesize, and recover `/goal` prompts for Claude Code and Codex. Each
goal is sized for the host that runs it, carries your standing guardrails
without retyping them, and is saved as a numbered revision you can find again
on any machine.

Claude Code caps a goal at 4,000 characters, counted in UTF-16 units, and its
evaluator judges only what the agent prints, so Claude goals target 3,800
characters (room for your addendum) and name printed evidence. Codex stores
the same 4,000-character objective, but its TUI moves longer text into a file,
so Codex gets the full objective. Both are saved as:

```text
<Documents>/YYYY-MM-DD/goals/<topic>-NNN.md
<Documents>/YYYY-MM-DD/objectives/<topic>-NNN.md
```

The goal is what you paste; the objective is the full statement it points to.
On WSL, `<Documents>` is your Windows Documents folder.

## Installation

From a shell, one command installs the plugin for Claude Code and adds the
marketplace first if it is missing:

```console
$ claude plugin install goal-planner --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install goal-planner@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add goal-planner@skills
```

Claude Code uses a leading slash (`/goal-planner:…`). Codex omits it
(`goal-planner:…`).

## Skills

Print a goal to paste, under the host's target, and save it. Also rewords a
draft, splits work into one goal per target, and adds an addendum:

```text
/goal-planner:print-goal [<what the goal is for>]
```

Build the next goal from the earlier ones, carrying every earlier task forward
with a recorded decision:

```text
/goal-planner:synthesize-goal [<what changed>]
```

Print a lost or earlier goal again, verbatim, from saved goals, Codex, or
prompt history:

```text
/goal-planner:recover-goal [current|previous|original|latest]
```

Each skill's flags are under `$ARGUMENTS contract` in its
`skills/<name>/SKILL.md`.

## How a goal is built

- `references/anatomy.md`: the sections of a goal and of an objective.
- `references/hosts.md`: what each host counts, who judges completion, and
  how each rendering differs.
- `references/modules.md`: the guardrails a goal can carry (research, spike
  method, adversarial review, commit and push policy, CI, resources, and more).
- `references/ledger.md`: where goals live and how they are numbered.
- `references/lineage.md`: how earlier goals carry into a new one.
- `references/history.md`: reading earlier goals from local prompt history.
- `templates/profile.md`: the profile that holds your defaults, at
  `~/.config/goal-planner/profile.md`.

## Scripts

`scripts/goal.py` measures, lints, saves, lists, and finds goals:
`measure`, `catalog`, `lint`, `ledger root|next|save|list`, and `find`. It
needs only the standard library.

## Prerequisites

- `python3` 3.9 or newer.
- `git`, for repository state.
- `uvx` (optional), to search prompt history with agentgrep.
- `gh` (optional), for pull-request and CI state.
