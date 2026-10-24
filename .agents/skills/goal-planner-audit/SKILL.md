---
name: goal-planner-audit
description: >-
  Use when explicitly asked to audit a goal against its original request,
  exact revision, evidence, exclusions, and acceptance conditions.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "<goal and specification> [original request, lineage, evidence, independent-review requirement]"
  source: "plugins/goal-planner/skills/audit/SKILL.md"
---

# Audit a goal

Review the exact draft against its sources and evidence without revising,
saving, activating, or executing it. Arguments: `$ARGUMENTS`.

Read [the contract](references/contract.md),
[safeguards](references/safeguards.md),
[rendering](references/rendering.md), and
[output contract](references/output.md).

`<planner>` is `references/planner.py`, resolved from this skill's directory
to an absolute path written literally in each command.

## 1. Bind the review

Build the contract's review packet under
[prose rules](references/prose-rules.md), reading full originals and using
[recovery](references/recovery.md) as needed. Inspect only relevant
current state. State reviewer independence under the safeguard rules; use a
fresh reviewer when required and report unavailable review as UNVERIFIED.

## 2. Check every obligation

Map every original requirement to its clause, acceptance, evidence, and
disposition. Check omissions, stale completion claims, contradictions, expanded
authority, missing holds, and exclusions reopened through derived checks.
Apply the contract's verdict distinctions and assess selected safeguards for
both effectiveness and necessity. Disputed constraints need concrete user
benefit; difficulty alone does not justify dropping an obligation.

## 3. Check the handoff

For a saved goal, verify its files with the selected host and applicable limit:

```console
$ python3 <planner> check \
    --goal <goal.md> \
    --host <claude-or-codex>
```

Use limit options only when selected. Apply the rendering reference's checks
for final counts, companion identity and reachability, and saved/printed
equality. Check full-contract coverage separately: mechanical success does
not establish it, and a path-only response fails despite a valid saved file.

## 4. Report findings

Report under [output contract](references/output.md) and
[prose rules](references/prose-rules.md), separating blockers from optional
recommendations and preserving disagreements and evidence gaps. Stop with the
review; editing or execution requires a separate instruction.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
