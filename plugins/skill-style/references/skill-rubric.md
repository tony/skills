# Skill writing rubric

The rules a SKILL.md is held to, and the reasoning behind the ones
whose reasoning is not obvious. The 500-line body, 64-character name,
and reserved-word limits come from Anthropic's skill authoring best
practices. The 150-character description limit, plugin boundaries, and
`disable-model-invocation` gating are house rules of this marketplace,
not host facts; check the project's AGENTS.md before applying them.

## Contents

- The deletion test, worked
- What the test never touches
- Naming
- Descriptions
- Sections and headings
- Progressive disclosure
- Degrees of freedom
- Workflows and feedback loops
- Terminology
- Library standards
- Anti-patterns
- Trigger testing

## The deletion test, worked

Delete the line. Name what the agent now does differently. No name, no
line.

The five costs that keep a line (command, constraint, trigger, output
contract, fork) are listed in the skill body.

Worked examples.

Cut — the agent already knows what a lockfile is:

```markdown
A lockfile records the exact resolved version of every dependency so
that installs are reproducible across machines. Most ecosystems ship
one.
```

Keep — names a constraint the agent would otherwise violate:

```markdown
Refresh the lockfile in its own commit. A lockfile bundled with a
source change makes the diff unreviewable.
```

Cut — restates the heading above it:

```markdown
## Running the tests

This section explains how to run the tests.
```

Keep — a fork with two defensible branches:

```markdown
Tracked file? Expand through `git ls-files`. Untracked? Treat the
argument as a literal path.
```

Cut — hedging that changes nothing:

```markdown
It is generally considered a good practice to review the output
carefully before proceeding, as this can help catch issues early.
```

Keep — the same idea as an instruction with a consequence:

```markdown
Confirm the plan before writing. An unreviewed batch edit is not
revertable file by file.
```

Every cut line above is *true*. Truth is not the bar; changed behavior
is.

### Block-level ablation

Run the test on whole sections too. A section whose lines each survive
in isolation still goes when the section as a whole describes the
agent's default behavior. "Analyze the code, then suggest
improvements" survives line by line and teaches nothing.

### The ledger

Before editing, write one bullet per proposed cut: the line, and the
reason nothing breaks. A cut you cannot justify in a bullet has not
been tested. Under `--audit`, the ledger is the whole deliverable.

## What the test never touches

The skill body lists the exempt lines. The reasons:

- **Frontmatter.** The host reads `name` and `description` alone before
  loading the body, so a weak description hides a perfect body.
- **Fences and commands.** A command in a skill is a quotation: the
  author verified it against a real system, and an edit silently
  unverifies it. Report a flaw in the ledger instead. Fence structure
  (tag, `$ ` prompt, one command per fence) is the one exception and
  edits no command character.
- **Headings.** An agent skims them to decide what to read; a body of
  undifferentiated paragraphs gets read partially or not at all.
- **Destructive-step warnings.** The cost of cutting one is paid by
  someone else, later, in a way no review catches.

## Naming

`name` takes lowercase letters, numbers, and hyphens, 64 characters or
fewer. It cannot contain XML tags, and it cannot contain the reserved
words `anthropic` or `claude`.

Pick one shape (`processing-pdfs`, `pdf-processing`, `process-pdfs`)
and keep it across a catalog.

`helper`, `utils`, `tools`, `documents`, `data`, and `files` name
nothing. A name that would fit twenty skills identifies none of them.

One job per skill. A name you cannot write without an "and" is two
skills, and splitting it is what lets either one route.

## Descriptions

The description is the only text that competes for the router's
attention. It decides whether the skill is ever used.

- **Third person, always.** The description lands in a system prompt,
  so `I can help you process Excel files` confuses the point of view.
  Write `Processes Excel files and generates reports`.
- **What it does and when to reach for it.** Both halves. A
  description with no trigger clause never fires.
- **The user's literal words.** A router matches text, not meaning. If
  people say "repo" and the description says "repository", the match
  is weaker than it looks. Write both where both get typed.
- **Front-load the trigger.** The first clause is what survives
  truncation and skimming.
- **Non-empty, no XML tags.** This library also caps it at 150
  characters; use the project's own cap when its AGENTS.md sets one.

Descriptions that route nothing: `Helps with documents`, `Processes
data`, `Does stuff with files`.

House rule: set `disable-model-invocation: true` on a skill that only
makes sense when asked for by name. It keeps the skill invocable while
removing it from the corpus every other description competes in.

## Sections and headings

The skill body states the section rules. The reasons behind two of them:

- State the rule before its exceptions. An agent that meets the edge
  case first has no model to hang it on, and generalizes the exception
  into the rule.
- Apply the reorder test: items that can be resequenced without
  changing meaning are siblings and belong in bullets. If reordering
  breaks them, they are an argument; write prose. Bulleting a causal
  chain hides the causality that was the point.

## Progressive disclosure

Only the metadata of every installed skill is preloaded, and hosts cap
that shared listing. The body loads when the skill is selected, and
bundled files load only when something reads them.

That gives a budget shaped like a funnel:

- **Description:** spend it on triggers.
- **Body:** under 500 lines. Everything a task needs *every* time.
- **Reference files:** everything a task needs *sometimes*. They cost
  nothing until read, so they can be long.

Keep every reference one level deep from the body. An agent that
follows a link out of a file it already followed a link into tends to
preview rather than read it (`head -100` instead of the whole thing)
and acts on a fragment. Link `reference/forms.md` from the body, and
never from inside another reference.

Give a reference file longer than 100 lines a contents list at the
top, so a partial read still shows the full scope of what is there.

Each layer answers a question the one above it did not. A reference
that restates the body in longer words is paid for twice and read
once; it should carry the cases, the worked examples, and the
exceptions the body only names.

Name files for their content: `form-validation-rules.md`, not
`doc2.md`. Organize by domain, so a question about sales loads the
sales file and nothing else.

## Degrees of freedom

Match specificity to how fragile the task is.

**High freedom — prose instructions.** Many valid approaches, decisions
depend on context. A code review is an open field.

**Medium freedom — a parameterized pattern.** A preferred shape
exists, variation is fine.

**Low freedom — the exact command, no parameters.** Fragile,
order-dependent, or destructive work is a narrow bridge. Give the
literal invocation and say not to vary it.

Over-specifying an open field wastes tokens and fights the model.
Under-specifying a narrow bridge is how data gets lost.

Reach for instructions before scripts. Ship a script when the work
needs deterministic behavior or external tooling the agent cannot
reproduce.

## Workflows and feedback loops

Pair anything quality-critical with a loop: produce, validate, fix,
re-validate, and only then proceed. The validator can be a script or a
reference file the agent checks itself against; the loop is what
raises quality, not the mechanism.

For batch or destructive work, add a verifiable intermediate: have the
agent write its plan to a file, validate the file, and only then
execute. Errors surface before anything is touched.

## Terminology

Pick one term per concept and repeat it. Mixing "field", "box",
"element", and "control" for one thing forces the reader to prove they
are the same. Consistency is not style here; it is parseability.

## Library standards

The skill body lists the defects and labels each as host fact or house
rule. The reasoning behind the ones that are not obvious:

- **Context expansion.** A `!` directly before a command's opening
  backquote expands on Claude Code, but a failing command or a missing
  `allowed-tools` grant empties the whole skill without an error. The
  form with the `!` inside the backquotes never expands, and Codex expands
  neither form. A numbered step that names what it gathers
  works everywhere.
- **Bundled files.** Codex does not substitute `${CLAUDE_PLUGIN_ROOT}`.
  Where several plugins ship the same file, each holds a vendored copy:
  edit the source, never the copy.
- **Tool grants.** `allowed-tools` pre-approves; only `disallowed-tools`
  removes a tool. `WebFetch` and `WebSearch` stay off a skill that
  reads untrusted input.
- **Portable shell.** `sed -i` differs between GNU and BSD/Darwin,
  `sed` `\+` and `\|` are GNU-only (use `-E`), and `readlink -f`,
  `stat -c`, `date -d`, and `mapfile` have no BSD equivalent. Temp
  files use `mktemp` with a template ending in `XXXXXX`.
- **State between commands.** Shell variables do not survive separate
  Bash calls. Do the work in one command, or print the value and use
  the literal afterwards.
- **Output contract.** Without a declared hero line, section order, and
  stopped-run shape, the agent invents headings and recap endings.
- **Analysis-then-execute skills** open execution with an
  orchestration-plan step the user approves.

## Anti-patterns

**Time-sensitive statements.** `Before August 2025, use the old API`
is wrong forever after. Put superseded behavior in a collapsed "old
patterns" section, or leave it out.

**Too many options.** `Use pypdf, or pdfplumber, or PyMuPDF, or…`
makes the agent choose badly. Give one default and one named escape
hatch for the case that needs it.

**Bare MCP tool names.** Qualify them as `ServerName:tool_name`, or
the agent fails to find the tool once a second server is connected.

**Explaining the domain.** The agent knows what a PDF, a lockfile, a
rebase, and a pivot table are. Skills carry what the agent cannot
know: your conventions, your constraints, your commands.

**Narrating the skill's own history.** No `previously`, no
`simplified`, no note that a section used to be longer. The file is
the current instruction set.

## Trigger testing

A description is not finished until it has been tested as a router
input.

1. Write three prompts a user would actually type, in their words, not
   the skill's.
2. Confirm this skill is the right answer to each.
3. Write one prompt that belongs to a neighboring skill, and confirm
   it goes there instead.
4. When a positive fails, the fix is almost always vocabulary: the
   user's word is missing from the description.

Beyond routing, build evaluations before writing the body. Run the
task without the skill first and record where the agent actually
fails; write only enough instruction to close those gaps. Skills
written from imagined failures document problems nobody has.

