---
name: skill-style
description: >-
  Use when writing, auditing, or trimming a SKILL.md, especially for bloated
  bodies, weak descriptions, or plugin-wide sweeps.
allowed-tools: ["Bash", "Read", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[skill paths/globs] [--audit] [--diff-only]"
  source: "plugins/skill-style/skills/skill-style/SKILL.md"
---

# Skill style

One bar: a line stays only when its removal would change what the
agent does.

## Two ways in

### Routed while authoring

Someone is writing or editing a SKILL.md. Apply the rules below to
that draft as it is written. Touch no other file, propose no sweep of
the rest of the catalog.

### Invoked by name with targets

Trim the named skills: build a ledger, edit in place, show the diff.
Never commits, never pushes, never needs a clean tree.

## `$ARGUMENTS`

- `paths/globs`: skill directories or `SKILL.md` files. Expand
  through `git ls-files` when tracked, else as literal paths.
- `--audit`: report the ledger and change nothing. This is the only
  use of the word "audit" below.
- `--diff-only`: show the proposed edits as a diff without writing
  them.

Empty `$ARGUMENTS` with no draft in play: ask which skills via
`ask-user-choice`. Never default to the whole repository. Without
`ask-user-choice` (Codex, headless), stop and say a skill path is
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
- `description`: 150 characters or fewer. Front-load the trigger.
  Never `I can help you…` or `You can use this to…`.
- `argument-hint` is required when the body consumes `$ARGUMENTS`.
- `allowed-tools` pre-approves, so list only tools a step uses, by
  bare name. Drop `WebFetch` and `WebSearch` unless a step fetches,
  and never pre-approve them on a skill that reads untrusted input.
- Set `disable-model-invocation: true` when the skill only makes sense
  asked for by name, so it stays out of the routing corpus.

## Library standards

Flag each as a defect; `references/skill-rubric.md` has the full
list and reasons.

- A `` ! `` immediately followed by a backtick-quoted command (context
  expansion). It never runs. Rewrite it as a numbered step that names
  what it gathers.
- A link or read that leaves the plugin, `the plugin root`, or a
  reference that sends the reader on to another reference. Bundled
  files are addressed by climbing out of the skill directory.
- A hardcoded language-specific command (a named test runner or
  package manager). Say "the project's test suite, as its AGENTS.md or
  CLAUDE.md defines it".
- An `ask-user-choice` step with no non-interactive default.
- A report-writing skill with no declared output shape, including the
  shape of a stopped run.

## Steps

1. **Load the house voice.** Read the project's `./AGENTS.md` and
   `./CLAUDE.md`. Read `references/skill-rubric.md` only when a
   rule needs its reasoning or an example. If the project ships a
   skill linter, run it for description length, headings, and
   `$ARGUMENTS` checks, and spend your own pass on the deletion test.
2. **Fix the description before touching a line of the body**, and
   test it: three prompts a user would type must match it, and one
   that belongs to a neighboring skill must not.
3. **Measure the resolved targets only.** Line counts locate the
   bloat. Skip this step for a draft in play.

   ```console
   $ wc -l <targets>
   ```

4. **Run the deletion test** and build the ledger. Include the
   library-standards defects.
5. **Confirm, then edit.** Show the ledger and confirm via
   `ask-user-choice` before writing; skip under `--audit` and
   `--diff-only`. Without `ask-user-choice`, edit only when the
   request explicitly authorizes it ("apply", "go ahead", "edit in
   place"); otherwise behave as `--diff-only`.
6. **Show the diff.** Skip under `--audit`.
   - Tracked target, edits written:

     ```console
     $ git diff -- <targets>
     ```

   - Untracked target, edits written: before editing, run
     `mktemp "${TMPDIR:-/tmp}/skill-style.XXXXXX"` and `cp` the target
     to the path it printed. After editing, run
     `git diff --no-index -- <copy> <target>` (exit status 1 means the
     files differ), then delete the copy. Do not name the copy in the
     reply.
   - `--diff-only`: write nothing. Show the edits as a unified diff in
     the reply.

## Output

Write it per `references/prose-rules.md`. No coded labels, no
bold lead-in on every bullet, no tables, no recap ending, no counts
of lines removed.

1. One hero line: the result, in one sentence.
2. `## Ledger`: one bullet per cut, quoting the line and why nothing
   breaks, then the library-standards defects and any command flaw
   reported but left as written.
3. `## Behavior changes`: edits that change what the skill does,
   separate from cuts. Omit when none.
4. `## Diff`: the diff from step 6. Omit under `--audit`.

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

## Diff

<the git diff from step 6>
```

## References

`references/skill-rubric.md` is the rule catalog;
`references/example-bloated.md` and
`references/example-ideal.md` show a skill before and after the
test.

## While trimming, do not add bloat

Replacements are concrete and shorter than what they replace. Never
narrate the edit inside the file: no *simplified*, no *previously*,
no note that a section used to be longer. The skill states its current
instructions and nothing about how it got here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
