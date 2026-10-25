# goal-planner

Print, reconcile, and audit complete goals without activating or executing
them. Claude Code and Codex support all four workflows, invoked by name.

## Installation

Add the Claude Code marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install goal-planner@skills
```

Add the Codex marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add goal-planner@skills
```

## Workflows

Draft from an outcome and current evidence:

```text
/goal-planner:print a Claude goal for the selected findings; save in my Documents folder
```

Reconcile earlier goals with new steering:

```text
/goal-planner:synthesize these two goals; investigate the CI failure first and retain the release hold
```

Audit against the original request and specification:

```text
/goal-planner:audit this goal and specification; check every requirement and authorization boundary
```

Save explicitly selected defaults:

```text
/goal-planner:profile save these defaults: Claude output, save-and-print, and independent review for delivery goals
```

In Codex, invoke the native plugin with `$goal-planner:print` and the other
skill names above; a standalone portable bundle uses `$goal-planner-print`.
Session permissions and holds remain in force; proposed future publication
instructions grant no present authority.

## Output and revisions

Claude defaults to **3,800 characters for the whole `/goal ` payload**, in both
Unicode code points and UTF-16 units, leaving room for addenda. Codex receives
the full objective unless an explicit user or delivery-interface limit applies.
The drafting assistant's host does not impose Claude limits on Codex output.

Printing and synthesis always display the complete payload, including after
saving or failure, followed by compact host, count, and save status. Material
gaps and synthesis dispositions follow when applicable; completed handoffs end
without a choice menu. Small goals need outcome, scope, authority, and
acceptance. Saving is opt-in through the request or approved profile;
explicit stdout-only forbids writes. The default root is `~/Documents`, with
an optional separate machine binding and local date:

```text
Documents/YYYY-MM-DD/goals/<topic>-NNN.md
Documents/YYYY-MM-DD/goal-specs/<topic>-NNN.md
```

A complete **goal specification** accompanies compact goals when needed.
Paired revisions continue across dates from `001`; prior files remain intact,
and unchanged reprints reuse the latest matching completed revision. Short
complete goals need no companion. Saved goal bytes match the printed payload.
Companion locators include digests and resolve from unrelated working
directories. Transfer both folders and render a new revision for changed paths.
Failed saving prints the full goal and required specification as incomplete;
it never permits manual publication that bypasses revision allocation.

## Prerequisites and references

The standard-library helper needs Python 3.9 or newer. Discover optional history
tools, reviewers, and probes when needed; agentgrep has separate runtime needs.
Profiles contain approved portable preferences; bindings hold local paths.
History supplies evidence/candidates, never implicit settings changes or upload.

Read the [contract](references/contract.md), [recovery](references/recovery.md),
[safeguards](references/safeguards.md), [rendering](references/rendering.md),
[profiles](references/profiles.md), and [output](references/output.md) rules.
The [eval suite](evals/README.md) exercises all workflows with synthetic inputs
through `claude plugin eval` and checks retained output files.
