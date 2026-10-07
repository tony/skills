---
name: skill-style
description: "Trims SKILL.md bodies by a deletion test and audits descriptions. Use when writing, trimming, shortening, or auditing a SKILL.md."
allowed-tools: ["Bash", "Read", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "[skill paths/globs] [--audit] [--diff-only]"
---

# Skill style

One bar: a line stays only when its removal would change what the
agent does.

## Two ways in

### Routed while authoring

Someone is writing or editing a SKILL.md. Apply the rules below to
that draft as it is written. Touch no other file, propose no sweep of
the rest of the catalog.

A draft pasted inline has no file: skip the confirmation and git, and
reply with the ledger and the diff of the paste (Steps, inline draft).

### Invoked by name with targets

Trim the named skills: build a ledger, edit in place, show the diff.
Never commits, never pushes, never needs a clean tree.

## `$ARGUMENTS`

- `paths/globs`: skill directories or `SKILL.md` files. Expand
  through `git ls-files` when tracked, else as literal paths.
- `--audit`: report the ledger and change nothing.
- `--diff-only`: show the proposed edits as a diff without writing
  them.

Empty `$ARGUMENTS` with no draft in play: ask which skills via
`AskUserQuestion`. Never default to the whole repository. Without
`AskUserQuestion` (Codex, headless), stop and say a skill path is
needed.

## The deletion test

Read the body one line at a time. For each, name the behavior that
changes when it is gone:

- A command that would not run, or would run with wrong arguments.
- A constraint the agent would violate: an ordering, a destructive
  step, a thing it must never do.
- A trigger that would stop firing.
- An output whose shape or format would drift.
- A fork the agent would take the wrong branch of.

Name one and the line stays. Name none and the line goes. *Adds
context*, *reads better*, *rounds it out*, and *harmless* are not
names; they are the absence of one.

Run it on whole blocks too. A section whose every line survives
individually still goes when the agent already does that by default;
the test asks what breaks, not what is true.

## Lines the test never touches

The test judges claims. These are not claims:

- **YAML frontmatter.** Held to whether it routes, not to whether it
  changes behavior (see the standard below).
- **Fenced code blocks, and every character of a command, path, flag,
  or snippet inside them.** Never reflow, shorten, modernize, or
  correct one; report a flaw in the ledger instead. Drop a whole
  fence only when a sibling fence teaches the same thing, never a
  line out of a fence's middle. The fence's structure is the one
  exception (see Sections).
- **Literal commands, paths, and flags in prose.** Backtick them and
  leave them alone.
- **Section headings.** They are the navigation an agent skims.
- **Warnings on destructive or irreversible steps.** A cut here is
  paid for by someone else.

Where a fence and its prose say the same thing, the prose goes.

## Sections

Bodies are sections, never a wall.

- One `#` title, then `##` sections. A heading names the step or the
  decision, not the topic: never `Context`, `Details`, `Notes`, or
  `Misc`.
- Steps that must run in order are a numbered list. Otherwise ask
  whether the items reorder without changing meaning: siblings are
  bullets, an argument is prose.
- State the rule before its exceptions.
- Prose runs at most three lines before a heading, a list, or a fence.
- Fence structure follows one policy, and fixing it never edits a
  command character. A single command run as-is is a `console` fence
  with a `$ ` prefix, one command per fence. A multi-line script is a
  `bash` or `sh` fence with no prompts. Comments go in prose outside
  the fence.
- A fence says when to run it and what its result means.
- Prefer nested sections over tables. A table earns its place only
  when the data is genuinely matrix-shaped.

## Frontmatter and description

The description is the only text a host sees before deciding. Write it
in third person, saying both what the skill does and when to reach for
it, in the literal words a user would type.

- `name`: lowercase letters, numbers, hyphens; 64 characters or fewer.
  `helper`, `utils`, and `tools` name nothing.
- `description`: 150 characters or fewer is this library's limit;
  use the project's own when its AGENTS.md sets one. Front-load the
  trigger. Never `I can help you…` or `You can use this to…`.
- `argument-hint` is required when the body consumes `$ARGUMENTS`. Add
  no field the body does not consume.
- `allowed-tools` pre-approves, so list only tools a step uses, by
  bare name. Drop `WebFetch` and `WebSearch` unless a step fetches,
  and never pre-approve them on a skill that reads untrusted input.
- House rule: set `disable-model-invocation: true` when the skill only
  makes sense asked for by name, so it stays out of the routing corpus.

## Library standards

Flag each as a defect in the ledger, labelled host fact or house rule.
`../../references/skill-rubric.md` has the full list and reasons.

### Host facts

These hold on the named hosts wherever the skill is installed.

- Context expansion: a `!` placed inside the backquotes, ahead of
  the command, never expands. A `!` directly before the opening
  backquote expands on Claude Code, but a failing or ungranted command
  empties the whole skill; Codex expands neither. Rewrite either form as a numbered step that names what it
  gathers and what a failure means.
- `${CLAUDE_PLUGIN_ROOT}` is not substituted by Codex. Address bundled
  files by climbing out of the skill directory.
- A hardcoded command that only fits one ecosystem (a named test runner
  or package manager) in a skill meant for any project. Say "the
  project's test suite, as its AGENTS.md or CLAUDE.md defines it".
- An `AskUserQuestion` step with no non-interactive default; Codex and
  headless runs have no such tool.

### House rules

These are this marketplace's limits. Apply them only when the project's
`AGENTS.md` or `CLAUDE.md` adopts them; elsewhere, do not import them.

- A link or read that leaves the plugin, or a reference that sends the
  reader on to another reference.
- A description over 150 characters.
- A workflow skill that only makes sense asked for by name and lacks
  `disable-model-invocation: true`.
- A report-writing skill with no declared output shape, including the
  shape of a stopped run.

## Steps

1. **Load the house voice.** Read the project's `./AGENTS.md` and
   `./CLAUDE.md`. Read `../../references/skill-rubric.md` only when a
   rule needs its reasoning or an example. If either file names a skill
   linter, run it for description length, headings, and `$ARGUMENTS`
   checks, and spend your own pass on the deletion test.
2. **Fix the description before touching a line of the body**, and
   test it: three prompts a user would type must match it, and one
   that belongs to a neighboring skill must not.
3. **Measure the resolved targets only.** Line counts locate the
   bloat. Skip this step for a draft in play.

   ```console
   $ wc -l <targets>
   ```

4. **Run the deletion test** and build the ledger. Include the
   library-standards defects. A rewrite never adds a claim the source
   did not make: list every added or changed claim, rename, and
   frontmatter change under Behavior changes. Report a flaw once, in
   one bullet, without speculating about edits nobody asked for.
5. **Confirm, then edit.** Show the ledger and confirm via
   `AskUserQuestion` before writing; skip under `--audit` and
   `--diff-only`. Without `AskUserQuestion`, edit only when the
   request explicitly authorizes it ("apply", "go ahead", "edit in
   place"); otherwise behave as `--diff-only`.
6. **Snapshot, edit, diff.** Skip under `--audit`. The script paths are
   relative to this file. Before any edit, snapshot every target; the
   first output line is the snapshot directory and each later line is a
   work copy and the label for it. The snapshot is what the diff
   compares against, so earlier uncommitted edits to a target never
   show as yours.

   ```console
   $ ../../scripts/skill_diff.py snapshot <targets>
   ```

   - Edits written: edit the targets in place, then diff against the
     snapshot.

     ```console
     $ ../../scripts/skill_diff.py diff <snapshot-dir>
     ```

   - `--diff-only`, or an unauthorized edit: write nothing to the
     targets. Edit the work copies, then diff against them.

     ```console
     $ ../../scripts/skill_diff.py diff <snapshot-dir> --work
     ```

   Then delete the snapshot, and never name its path in the reply.

   ```console
   $ ../../scripts/skill_diff.py clean <snapshot-dir>
   ```

   - Inline draft: run `mktemp -d "${TMPDIR:-/tmp}/skill-style.XXXXXX"`,
     write the pasted text to `SKILL.md` inside the directory it
     printed, snapshot that file, edit its work copy, diff with
     `--work`, and clean up. No confirmation, no git. The diff labels it
     `SKILL.md`.

## Output

Write it per `../../references/prose-rules.md`. No coded labels, no
bold lead-in on every bullet, no tables, no recap ending, no counts
of lines removed, no local or temp paths.

1. One hero line: the result, in exactly one sentence, with no second
   sentence about what survives. Anything more goes in the Ledger.
2. `## Ledger`: one bullet per cut, quoting the line and why nothing
   breaks, then the library-standards defects and any command flaw
   reported once and left as written.
3. `## Behavior changes`: edits that change what the skill does,
   separate from cuts: renames, added claims, frontmatter changes.
   Omit when none.
4. `## Diff`: the diff from step 6 in a `diff` fence. Omit under
   `--audit`.

Use these headings verbatim and no others: a flaw left alone is a
Ledger bullet, never a `## Cuts` or `## Still open` section.

A stopped run (no targets, missing file, edit not authorized) is one
sentence stating the result, then what the user must supply or
authorize. No sections.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
db-helper loses its explanatory padding; commands and warnings stay.

## Ledger

- "A database is a system for storing data": the agent knows this.
- "This section explains how to restore": restates the heading.
- Description says "I can help you"; rewrite in third person.

## Behavior changes

- Name changes from `helper` to `db-helper`; callers must update.

## Diff

--- a/SKILL.md
+++ b/SKILL.md
@@ -1,4 +1,4 @@
-name: helper
+name: db-helper
```

## References

`../../references/skill-rubric.md` is the rule catalog;
`../../references/example-bloated.md` and
`../../references/example-ideal.md` show a skill before and after the
test.

## While trimming, do not add bloat

Replacements are concrete and shorter than what they replace. Never
narrate the edit inside the file: no *simplified*, no *previously*,
no note that a section used to be longer. The skill states its current
instructions and nothing about how it got here.
