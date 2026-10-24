# Goal anatomy

Contents: The goal, The objective, Writing the done-when clause, Bounding the run, Example.

A goal is the text the user pastes after `/goal`. The objective is the full
statement a goal points to when the whole of it does not fit, and the text
Codex runs directly. Both are saved per `ledger.md`; how each host counts and
judges them is in `hosts.md`.

## The goal

Sections in this order, each a short paragraph. Leave out a section with
nothing to say; never pad one.

1. End state: one or two sentences naming what is true when the work is done.
2. Read first: the objective revision as an absolute path, called required
   context, plus any lineage or findings file the work rests on. When earlier
   work exists, say that earlier delivery and green CI do not establish
   acceptance under this goal.
3. Authority: branch and worktree, commit style, push target (none, a private
   mirror, or origin), pull request or not, and what must not change. End with
   "This goal authorizes nothing beyond itself."
4. Method: the skills to use in the host's syntax, the order, serial or
   parallel, and when to use subagents.
5. Guardrails: the enabled modules from `modules.md`, in their compact form.
6. Done when: each criterion with the evidence the agent prints.
7. Bound: for Claude, a turn or time clause, the turn-counter line, and what
   to print and do when one blocker repeats. Codex injects its own blocked
   rule, so a Codex goal carries a bound only when the user asked for one, and
   never a blocker rule.

## The objective

The objective carries what the goal cannot:

1. End state, in full.
2. Starting state: branch, pull request, head SHA, and what earlier goals
   established, each tied to the revision it was checked at.
3. Tasks: one line per task with a stable key (`F1`, `parser-tests`) and its
   acceptance evidence. Keys never change across revisions; a dropped task
   keeps its key and says why.
4. Modules: each enabled module in its full form.
5. Findings: the full lists the conversation produced. This is where an
   overflow of findings goes; it is a section, never a separate file.
6. Lineage: per `lineage.md`, when the objective was synthesized.
7. Done when and bound, repeated from the goal.

## Writing the done-when clause

Claude's evaluator reads the condition and the conversation and nothing else,
so each criterion names something the agent prints:

- the task table with PASS or FAIL and the commit for each key;
- each gate command from the project's AGENTS.md with its exit status, run
  after the last commit;
- `git status -sb`;
- the last line from the resource-guard skill;
- the pull request's checks on the exact head, when pushing is authorized.

A criterion the agent cannot print, such as "the code is clean", is judged on
the agent's word. Rewrite it as evidence or cut it. Codex judges its own goal
under an audit it injects every turn, so a Codex done-when clause lists the
requirements and leaves the audit out.

## Bounding the run

In a Claude goal, write the bound and the counter together: "Or stop after 40
turns. End every turn with the line `turn N of 40`." In tests with a bound of 5, the counter
stopped the loop after exactly 5 turns; replies with nothing countable ran a
turn late, and prose about a blocked task never reached the bound before
Claude Code's own block cap ended it. For a blocker: "If the same blocker
repeats for 3 turns, print it with its evidence and stop."

## Example

A Claude goal for "address all the issues found above, same branch, local,
commit often", with `<documents>` printed as the resolved path:

```text
/goal Resolve every finding in objective storages-001 on branch storages-20261024 in its own worktree; local only.

Read first: <documents>/2026-10-24/objectives/storages-001.md (keys F1-F9, acceptance per key). It is required context.

Authority: one commit per finding in the project's commit style. Never push, open pull requests, or touch other branches. This goal authorizes nothing beyond itself.

Method: spike-ratchet any finding whose fix is uncertain. Before calling a convention accidental, check `git log -S` and prompt history. Use subagents only for independent findings.

Guardrails: no test or comment bloat; test behavior, not implementation. Run goal-planner-resource-guard before each build; below the reserves, halve parallelism and clean only this goal's artifacts.

Done when, printed in this conversation: (1) the objective's task table with PASS and the commit SHA for every key; (2) the AGENTS.md gates with exit 0 after the last commit; (3) `git status -sb` clean; (4) the last resources line. If one blocker repeats for 3 turns, print it with its evidence and stop. Or stop after 40 turns; end every turn with the line `turn N of 40`.
```
