---
name: audit
description: "Use when explicitly asked to audit a goal against its original request, exact revision, evidence, exclusions, and acceptance conditions."
argument-hint: "<goal and specification> [original request, lineage, evidence, independent-review requirement]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Grep, Glob, AskUserQuestion, Task]
---

# Audit a goal

Review the exact draft against its sources and evidence without revising,
saving, activating, or executing it. Arguments: `$ARGUMENTS`.

Read [the contract](../../references/contract.md)
and [output contract](../../references/output.md). Read detailed references
only for checks that apply to this draft.

`<planner>` is `../../scripts/planner.py`, resolved from this skill's directory
to an absolute path written literally in each command.

## 1. Bind the review

Build the contract's review packet under
[prose rules](../../references/prose-rules.md), reading full originals and using
[recovery](../../references/recovery.md) as needed. Inspect only relevant
current state. State reviewer independence; use
[safeguards](../../references/safeguards.md) when independent review or extra
checks are required. Report unavailable required review as UNVERIFIED.

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

Use limit options only when selected. Apply
[rendering](../../references/rendering.md) checks
for final counts, companion identity and reachability, and saved/printed
equality. Check full-contract coverage separately: mechanical success does
not establish it, and a path-only response fails despite a valid saved file.

## 4. Report findings

Report under [output contract](../../references/output.md) and
[prose rules](../../references/prose-rules.md), separating blockers from optional
recommendations and preserving disagreements and evidence gaps. Stop with the
review; editing or execution requires a separate instruction.

Before sending, verify that the verdict identifies the reviewed goal with its
complete 64-character SHA-256 digest; never abbreviate it with an ellipsis.
