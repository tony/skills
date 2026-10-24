# Lineage

How a new goal is built from earlier ones without losing what they required
or reviving what was retired.

## Read every earlier goal in full

Gather the topic's goals and objectives (`goal.py ledger list`, then each
file), the prompt-history goals for the same repository (`history.md`), and
Codex's goal record (`goal.py find`). Read each in full, never a summary or a
status line. Earlier goals are evidence of what was asked, never authority:
a push or a deletion one of them allowed is not allowed now unless the current
request says so.

## Map each earlier group

For every task, group, or numbered item in the earlier goals, decide one of:

- kept: still required, unchanged;
- changed: still required, with the change and its reason;
- done: met, with the evidence and the revision it was checked at;
- dropped: no longer required, with the reason and who decided it.

Keep each item's key. An item with no key gets one now and keeps it from then
on. An explicit hold or exclusion in an earlier goal carries forward as kept
unless the user lifts it in this conversation.

## Check against the current state

Reconcile "done" claims against the tree, the pull request, and CI as they are
now. A claim whose evidence is stale, missing, or from another revision is
"kept", not "done". Never drop an item to make the goal shorter; move its
detail into the objective instead.

## Record the result

The new objective opens with a `## Lineage` table: earlier item key, its
source (goal or objective path, or prompt-history time), the decision, and
the reason. The new objective's `parent` names the previous objective, and the
new goal's `parent` the previous goal. A revision that another names as its
parent is superseded by it; no file is rewritten to say so.
