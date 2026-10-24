---
name: resource-guard
description: "Use when a goal or long run must watch CPU, memory, and free disk space, or clean up its own build artifacts to save space."
argument-hint: "[check|sample <command>|register <worktree>|clean] [--apply]"
allowed-tools: ["Bash", "Read"]
---

# `/goal-planner:resource-guard`

Keep the machine usable while a goal runs: read free space, inodes, memory,
and pressure against the reserves, print one line the goal's evaluator can
see, and clean only build artifacts in worktrees the goal created. A goal can
call this every turn.

## `$ARGUMENTS` contract

- `check` (default): compare the readings with the reserves.
- `sample <command>`: run one expensive command and report its time and peak
  memory.
- `register <worktree>`: record a worktree the goal created, so its artifacts
  can be cleaned later.
- `clean`: list the artifacts that would be removed. `--apply` removes them,
  and only when the request or the active goal says to clean up artifacts.

## Step 0: Resolve the script and the reserves

`<resources.py>` is `../../scripts/resources.py`, resolved from this skill's
own directory; write it as an absolute path in every command. Run each command
by itself, with no `cd`, `;`, `&&`, pipe, or shell variable, so a single
permission rule for `python3` covers every call. The reserves are in
`../../references/resources.md`; the profile's `reserve_*` and
`*_pressure_pct` values replace them when set.

## Step 1: Check

Check the worktree and the Documents root that holds the goal's evidence:

```console
$ python3 <resources.py> check \
    --path <worktree> \
    --path <documents>
```

Copy its first line into the reply word for word; that line is what Claude's
evaluator reads. Exit 1 means a reserve is breached.

## Step 2: On a breach

Follow "On a breach" in `../../references/resources.md`: stop launching work,
halve parallelism, look for leaks the goal owns, then list its artifacts with
`clean`. Never lower a reserve to clear a breach. When the goal's own
artifacts are not the cause, say what the readings show and suggest
`/disk:disk`.

## Step 3: Sample, register, or clean

Run the matching command from `../../references/resources.md` for `sample`,
`register`, and `clean`. Keep the manifest outside every worktree, beside the
goal's objective. `clean` without `--apply` deletes nothing; report what it
would remove and every refusal with its reason.

## Output

Write it per `../../references/prose-rules.md`. In this order:

1. The `resources ok` or `resources low (...)` line, verbatim.
2. `## Readings`: free space and inodes per path, available memory, load,
   and pressure, with any reading the platform does not report named as
   unknown.
3. `## Breaches`: each breach and what was done about it, when any.
4. `## Cleanup`: removed, would remove, and refused, when `clean` ran.
5. When a breach needs a decision (clean, stop, or keep going) and this is
   not a goal turn, ask with `AskUserQuestion`; without a question tool, print
   the options as a plain list. Inside a running goal, report and continue.
