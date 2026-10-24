# Guardrail modules

Contents: Choosing modules, Quality and method, Research and review, Repository and CI, Scope and pacing, Machine and cleanup.

Each module is a guardrail a goal can carry. A module has trigger words that
switch it on, a default, a compact form for Claude, a full form for Codex and
the objective, and the profile keys it fills. `{braces}` are profile values;
the user's own wording for a module, when the profile has it, replaces the
form below.

## Choosing modules

1. Start from the profile's defaults (`## <module>: on|off|auto` sections);
   `auto` uses the module's own default below.
2. Turn modules on or off by the request's words: the triggers below, "skip",
   "no", "without".
3. Turn on what the repository shows it needs: CI configured turns on
   `ci-proof`; a changelog file turns on the changelog rule in `vcs-policy`.
4. Leave out a module whose guard the task cannot trip. A docs-only goal
   needs no `resources`; a research-only goal needs no `vcs-policy` push
   line. Name every module left out in the print-goal output's Modules section.

## Quality and method

### quality-bar

- Triggers: "effort doesn't matter", "blast radius", "elite".
- Default: on.
- Claude: Effort and blast radius do not matter; aim for the best {artifact} of its kind.
- Codex: Effort does not matter and blast radius does not matter. Aim for the best {artifact} of its kind, judged by the rubric.

### method-ratchet

- Triggers: "spike", "ratchet", "bakeoff", "probe", "graft".
- Default: on for code changes.
- Claude: the `spike-ratchet` skill each uncertain change in whatever order works best; loop back to root causes, graft, confirm; once proven, rewrite cleanly.
- Codex: $spike:ratchet each uncertain change, in whatever order the evidence unblocks. When something fights back, research the root cause, bake off the competing fixes, graft the winner, and confirm. Once proven, rewrite cleanly from scratch using what was learned.

### rubric

- Triggers: "rated", "9.5/10", "score".
- Default: on.
- Claude: Rate the result {target}/10 or better on {dimensions}; print each score with its evidence.
- Codex: Rate the result on {dimensions}. Anything below {target}/10 on one of them is unfinished work, with the evidence for each score.
- Profile: `rubric_target`, `dimensions.<domain>`.

## Research and review

### research-corpora

- Triggers: "study", "research", "~/study", "notes".
- Default: on.
- Claude: Research with rg, ag and fd (not grep and find) in {study_roots}; check prompt history and `git log -S` before calling a convention accidental.
- Codex: Study the sources in {study_roots} with rg, ag and fd. Before calling an existing convention accidental, find its rationale with `git log -S` and a prompt-history search (`history.md`).
- Profile: `research_roots`.

### adversarial-review

- Triggers: "adversarial", "judge", "reviewer", "staff engineer".
- Default: on.
- Claude: Have independent adversarial reviewers, each idiomatic in {review_lenses}, judge each change; done only when they find nothing material.
- Codex: Independent adversarial reviewers, one per lens in {review_lenses}, judge each change and the final branch. One reviewer takes the adoption view: choosing between building this in-house and adopting it, what is missing, what should differ, what should not be there? Done only when the answer is adopt with nothing material left.
- Profile: `review_lenses`.

## Repository and CI

### vcs-policy

- Triggers: "commit often", "force push", "worktree", "branch", "don't push".
- Default: on for code changes.
- Claude: Work in {worktree_pattern}; commit often in small coherent commits; {push_rule}.
- Codex: Work in a worktree at {worktree_pattern}. Commit often, one coherent change per commit, in the project's commit style; a changelog entry never shares a commit with code. {push_rule}.
- `{push_rule}` with no push target (`push_target: none`, or the request says local): "Never push; replace an attempt that failed with a soft reset". With a target: "Push only to {push_target}; replace a pushed attempt that failed with a soft reset and `git push --force-with-lease --force-if-includes`; {pull_request}".
- Profile: `worktree_pattern`, `push_target`, `pull_request`, `private_remote`.

### ci-proof

- Triggers: "CI", "gh pr checks", "checks pass".
- Default: on when CI is configured and pushing is authorized; off otherwise, whatever the profile says.
- Claude: Watch the checks on the exact pushed head; some hunches only CI can settle; print the final checks.
- Codex: Watch the pull request's checks on the exact pushed head (`gh pr checks --watch`). Some hunches can only be settled by pushing and reading CI. A check that never ran is not green.

### anti-slop

- Triggers: "cruft", "bloat", "verbosity", "slop".
- Default: on.
- Claude: No verbosity, test bloat or comment bloat; test behavior, not implementation.
- Codex: Avoid verbosity everywhere: in code, comments, docs, commit messages, and reports. No test bloat or comment bloat; test behavior, not implementation; condense rationale to the decision and its consequence.

### downstream-safety

- Triggers: "downstream", "blockers", "other PRs".
- Default: off.
- Claude: Create no blockers for other open pull requests or issues.
- Codex: Check each change against the other open pull requests and issues and create no blockers for them; small ambiguities can be ignored.

### breaking-changes-ok

- Triggers: "backward compatibility doesn't matter", "not a stable API", "rename".
- Default: off.
- Claude: No backward-compatibility burden, but every rename reaches every instance.
- Codex: The API is not stable: no deprecation or legacy shims. A rename or changed behavior reaches every instance in the tree in the same change.

## Scope and pacing

### scope-holds

- Triggers: "research only", "don't action", "skip", "not in CI", "out of scope".
- Default: on whenever the request excludes anything.
- Claude: Out of scope: {exclusions}. Printing this goal does not activate it.
- Codex: Out of scope, and not to be added: {exclusions}. Printing or saving this goal prepares a handoff only; nothing runs until the user sets it.

### serial-issues

- Triggers: "one at a time", "serially", "independently".
- Default: off.
- Claude: Take the issues one at a time, each in its own commit.
- Codex: Take each issue independently and serially: research, probe, review, and commit one before starting the next. Different issues' probes and commits never overlap.

### subagents

- Triggers: "sub-agents", "subagents", "parallel".
- Default: on, capped.
- Claude: Use subagents for independent work only, at most {subagent_cap} at once; the coordinator alone commits and pushes.
- Codex: Use subagents for independent work only, at most {subagent_cap} at once. Every subagent brief says the coordinator alone commits, resets, stashes, and pushes.
- Profile: `subagent_cap`.

### honest-stop

- Triggers: "never claim done", "admit", "stop and ask".
- Default: on for Claude; Codex injects its own.
- Claude: Never call the work done when it is not; when stuck, stop and say what advice is needed.

### hand-test

- Triggers: "hand test", "dev server", "URL", "QA".
- Default: off.
- Claude: Before sign-off, start a dev server and print a URL for the user to test by hand.
- Codex: Before sign-off, run the real workflow by hand: start a dev server or the CLI, exercise a success path and a meaningful failure path, and give the user a URL or command to repeat it.

## Machine and cleanup

### resources

- Triggers: "watch cpu", "memory", "free space", "disk", "build artifacts", "save space".
- Default: on for builds and test suites.
- Claude: Run the `goal-planner-resource-guard` skill before each expensive command; below the reserves, halve parallelism and clean only this goal's artifacts; print its line.
- Codex: Run $goal-planner:resource-guard before each expensive command and print its line. On a breach, stop launching work, halve parallelism, and clean only the build artifacts of worktrees this goal registered. Never lower a reserve to hide a breach.
- Profile: `reserve_disk_gib`, `reserve_inodes`, `reserve_mem_gib`, `cpu_pressure_pct`, `mem_pressure_pct`.
