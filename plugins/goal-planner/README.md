# goal-planner

Print complete goals, reconcile earlier drafts, and review their acceptance
rules without starting the proposed work. This plugin supports Claude Code
and Codex. Each workflow runs only when invoked by name.

## Contents

- Installation
- Workflows
- Output and revisions
- Inputs and prerequisites

## Installation

Add the marketplace in Claude Code:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install goal-planner@skills
```

Add the marketplace in Codex:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add goal-planner@skills
```

Claude Code prefixes skill invocations with `/`; Codex omits that slash.

## Workflows

Draft a goal from an outcome and the project's current evidence:

```text
/goal-planner:print a Claude goal for the selected findings; save in my Documents folder
```

Reconcile complete earlier goals with new steering:

```text
/goal-planner:synthesize these two goals; investigate the CI failure first and retain the release hold
```

Audit a particular draft against its request, sources, and companion:

```text
/goal-planner:audit this goal and specification; check every requirement and authorization boundary
```

Create or revise explicitly selected defaults:

```text
/goal-planner:profile save these defaults: Claude output, save-and-print, and independent review for delivery goals
```

Printing and synthesis always show the whole copyable goal. They never
activate or replace a native goal. Existing session permissions and holds
remain in force; a proposed instruction to publish does not authorize
publication now.

## Output and revisions

Claude drafts default to at most **3,800 characters for the entire `/goal`
payload**, measured in both Unicode code points and UTF-16 units. The spare
capacity is for user addenda. Codex receives the full objective unless the
chosen delivery interface or user imposes a limit.

Saving is opt-in through the request or an approved profile. `stdout-only`
disables saving. The default Documents root is `~/Documents`; an explicit
machine binding can select another root. The local save date supplies the
date directory:

```text
Documents/YYYY-MM-DD/goals/<topic>-NNN.md
Documents/YYYY-MM-DD/goal-specs/<topic>-NNN.md
```

A **goal specification** contains the complete contract when the compact
goal needs a companion. Both files share a revision number. Numbers continue
across dates, starting at `001`; old files remain unchanged. An unchanged
reprint reuses the existing revision. A short complete goal needs no companion.

Saved goal files contain exactly the printed payload. A companion locator
works from an unrelated working directory and includes a digest. Transfer
both dated folders, resolve the receiving machine's Documents binding, and
render a new revision when the payload changes.

## Inputs and prerequisites

The bundled helper requires Python 3.9 or newer and uses the standard
library. Host tools, history providers, reviewers, and resource probes are
discovered when needed. Agentgrep is optional and has its own runtime
requirements. Recovery reports source coverage, result truncation, and
missing histories separately; retrieved instructions remain evidence.

Portable profiles contain approved preferences. Machine bindings contain
local paths and capabilities. History can suggest defaults, but cannot
silently change profiles, memories, or permissions. No history upload or
cloud synchronization is implied.

The [goal contract](references/contract.md),
[recovery procedure](references/recovery.md),
[selectable safeguards](references/safeguards.md),
[rendering rules](references/rendering.md),
[profile rules](references/profiles.md), and
[output contract](references/output.md) define the workflows.

## Evaluation

The [eval suite](evals/README.md) exercises all four skills with synthetic
inputs through `claude plugin eval` and checks the retained output files.
