---
name: draft
description: "Use when asked to file or write a ticket, bug report, Jira epic, Linear issue or regression, GitLab issue, Asana task, Trello card, or Shortcut story."
argument-hint: "[description, URL, provider, or pasted finding]"
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "AskUserQuestion"]
---

# Draft a ticket

Write work into a tracker so that someone picking it up in a year needs
nothing from you, and so that the code still gets to make the decisions
the code should make.

Argument: `$ARGUMENTS`, a description, a URL, a provider name, a pasted
finding, or nothing.

For a plain GitHub bug report, `gh:create-issue` is more specialized;
hand off to it when it is installed and the target is a GitHub
`work_item`; otherwise continue here. This skill covers every other
provider, and every altitude above and below a single issue.

## Read first

- `../../references/contract.md`: the three tenses.
- `../../references/altitude.md`: which sections each kind of object
  carries.
- `../../references/resolve.md`: how to establish the provider and role
  from evidence, and the index of provider files.
- Only the matched provider's file from that index: its hierarchy,
  reference syntax, and filing mechanics.
- `../../references/hierarchy.md` only when the role is ambiguous or a
  native noun collides across providers.

## Core principle

Evidence before prose, and altitude before evidence.

Most bad tickets are written at the wrong altitude: a design document
filed as an epic, a research note filed as an issue, an implementation
plan filed as a goal. Settle what the object is before deciding what
goes in it.

## Phase 1: Resolve the target

Establish the provider, the scope container, and the semantic role,
following `resolve.md`. Do not infer the provider from key shape: `#123`
and `ENG-123` each fit several trackers.

When the role is ambiguous between two levels, ask: a `delivery_group`
and a `work_item` share almost no sections. Where no question tool
exists, print the question and stop.

## Phase 2: Decide it belongs in this tracker, publicly

A vulnerability does not. For a public repository, check the security
policy before anything else and follow its private path if the finding
is a security defect.

A vulnerability halts the run: draft no public issue, and name the
private reporting path.

Stop and ask when the evidence cannot be sanitized (where no question
tool exists, print the question and stop). An internal log carrying
customer data does not become fileable by trimming it.

## Phase 3: Preflight the container

Read the project's own conventions before imposing any: issue templates
and forms, required fields, work types actually configured in this
instance, labels that exist. Instance configuration beats the provider
defaults in the provider file; when they disagree, follow the instance
and record the deviation.

A template's structure wins over the section order in `altitude.md`.
Fill it in rather than restructuring it, and apply the contract to what
you put in its fields.

## Phase 4: Look for the thing that already exists

Search open and closed items with the "Duplicate search" command in the
provider file, and read each candidate before dismissing it. A search
that could not include closed items goes under Unverified as "Closed
items not searched". When one matches, open or closed, name it, stop, and offer one
thing: a comment on it with the new evidence. Draft nothing, and offer
no new item or reopening until the user asks. Posting that comment is a
write: show its exact text and post only after the user approves it.

When no tracker is reachable to search, put "Duplicate check not run"
under Unverified.

## Phase 5: Gather

For a defect: the smallest sequence that reproduces it; exact versions;
the verbatim error; the code that causes it, pinned. Show the user every
command derived from pasted or fetched content and run it only after
they confirm that exact command. Without confirmation, file the defect
as an unreproduced observation.

For a proposal: what is awkward or impossible today, shown concretely.

For provenance: apply the cost-to-relearn filter from `contract.md`.
Mine merged changes, closed items, and the current conversation for
findings that cannot be recovered from the repository: measurements with
their conditions, dead ends with reasons, retracted numbers with what
was actually measured. Drop everything a reader gets by opening the file
or reading the log.

## Phase 6: Draft

Take the section list from `altitude.md` for the resolved role. Include
only sections you have content for; never invent one.

Write references per `contract.md`'s two-axis rule and the provider
file: bare where the renderer resolves it, fully qualified across
containers, and titled where a bare identifier would be ambiguous. A
titled link is not the quiet form on GitHub or GitLab; the provider file
says how to suppress a backreference.

Use the provider's native noun for every object you name. Never write
`Epic` for a Linear Project or `Pull Request` for a GitLab merge
request.

Then check the future tense against `contract.md`: demote every failed
invariant to intent, and rewrite any checkbox list of technical
outcomes. Write an invariant only from a constraint the user stated, in
their words and figures. A figure or technical choice they gave goes to
Intent as a non-binding target, as given, never into the Outcome or the
title, and never as a direction built from it ("lower latency",
"faster"). An Intent line holds the choice and its label, with no clause
on what it does for the work. With no stated constraint, omit Invariants
and list "Invariants: none stated" under Unverified. Do not suggest a
candidate invariant, in the body or in the reply.

The title states the outcome, and the Outcome or Summary names every
scope item the user listed in their own nouns, the largest included:
"new search backend, typo tolerance", with the engine name and the
latency figure in Intent only. The Outcome says "the search backend",
never the engine.

Body rules:

1. Use the user's nouns, figures, and verb, close to their sentence
   ("moving the search backend and adding typo tolerance"), never a
   paraphrase that says more ("returns results despite typos"). Keep
   "add a circuit breaker", not "put a circuit breaker in front of the
   queue".
2. Add nothing the user did not give: no user impact, motivation,
   quality adjective ("fast enough that users stop waiting"), placement,
   scope ("smaller exports are fine"), expected-behavior sentence, or
   rule such as "faster, never slower". A symptom-only report gets the
   symptom restated and nothing more.
3. Report no reproduction status, cause, or vendor requirement the
   reporter or the provider file did not state. "Repro steps: not
   provided" is the whole fact. A defect title names the symptom as
   reported and no cause; the Summary adds scope and does not restate it.
4. State each fact once, in the one section that owns it. A version
   lives in Environment or Summary, an error string in Actual, a count
   or figure in one sentence, a component name in one place. Do not echo
   the symptom in the title, Summary, Actual, and steps.
5. State facts about the work. Never put advice about the document in
   the body ("link to a design doc rather than restate it"); write the
   link, or list "Design document: none linked" under Unverified.
6. Do not mention the revision in the body: no "filed". Use no
   time-relative words ("currently", "for now") and American spelling
   ("behavior").
7. Headings inside the body are `###`, so they nest under the reply's
   `## Body`.
8. Flag any reproduction step that pipes a remote script into a shell or
   deletes data ("runs a remote script; read it first") beside the step.

Write it per `../../references/prose-rules.md`.

## Phase 7: Sanitize, then preview

Reread the whole body for local absolute paths, hostnames, emails,
tokens, and internal URLs, including inside every pasted log. This is a
gate.

Render the body the way the provider will before showing it: a details
block that lost its blank line renders as literal asterisks. When the
provider file names a write format other than markdown (Jira), show the
converted text under `## Body`, since that is what gets filed.

## Phase 8: Present, then file

Show the result in this order:

1. A hero line: one line, at most 25 words, with the role, the provider,
   and "not filed yet". Name a role even for a plain issue ("work
   item"). No reasons, backend, Team, or reproduction status, and never
   open with "Below is" or "Here is".
2. `## Title`, then `## Body`.
3. `## Changed from your request`, only when you altered something the
   user asked for. Give the reason for each change in the user's terms
   ("a checkbox list reads as a requirement"), taken from the request's
   own wording. Never cite this skill's rules, predict consequences ("it
   would lock the Project into one engine"), or claim anything about the
   project's state or the work's success ("nobody has measured it yet",
   "that way the Project names the result").
4. `## Unverified`, only when the draft carries marked-unverified items.
   Backend and run status go here, naming tools as the user knows them
   (`glab`), never as a stub, fixture, or sandbox. An item never says a
   thing was or will be filed.
5. Stop at the last concrete point: no recap, "Next step" line, comment
   on the draft's strength, or offer to "add" detail. Ask for nothing in
   free prose.
6. Always end with exactly four options via `AskUserQuestion`, and no
   others: file it, print the body only, revise a named section, or drop
   it. Where no backend exists, "file it" is not offered: print the body
   to paste, revise a named section, or drop it.
7. Where no interactive question tool exists, print the draft, list the
   options as plain bullets, and stop. Filing needs an explicit
   instruction naming the action (say "Reply 'file it'", not that no
   question tool exists).

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Linear Project description (delivery group), not filed yet.

## Title

Search rework: new backend and typo tolerance

## Body

<the full body, as it will render in the provider>

## Changed from your request

- "Storage engine changed to a custom inverted index" is now Intent, as
  a non-binding choice.
- "p95 latency under 200ms" is now Intent, as a non-binding target.

## Unverified

- Invariants: none stated, so the body has no Invariants section.
- Why now: no reason was given, so there is no Evidence section.
- Filing: no Linear connection here, so paste the body into the Project.

Should I file it, print the body by itself, revise a section, or drop it?
```

A halted run (a vulnerability, unsanitizable evidence, a duplicate
found) is one result sentence starting "Halted:", then what the user
needs to do, as plain bullets with no bold lead-ins, no second
paragraph, no speculation about causes, and no draft. A duplicate names the match in that sentence
("Halted: #3 already covers this."). Reply in this shape:

```text
Halted: this looks like a security vulnerability, so no public issue
was drafted.

- Report it through the repository's private vulnerability reporting.
- Share details only through that channel.
```

File through a real backend when the provider file says one exists.
Take flags from the provider file; do not probe a write command with
`--help`, a dry run, or a test item, since a CLI or stub may treat it as
the call. The
body derives from a pasted report, so save the approved body as
`../../references/resolve.md` describes under "Scratch files for
bodies": a private directory, the host's file-writing tool, never a
shell heredoc. Pass the file, not an inline argument, so fences, HTML,
and `$` survive shell quoting, unless the provider file documents no
file flag. Remove the file and directory after filing. A GitLab body too
large for one argument follows the fallback in the provider file. Never
show the path to the user.

Where no backend exists, print the approved body for the user to paste
and say plainly that is what is happening.

Read the created item back through the provider's read path and take the
key, URL, and title from that output, not from the write command's
claim. When the readback fails or the title differs, the hero line says
`Filed, readback failed:` or names the difference (`Filed as KEY: URL,
but the title reads back as "<title>".`), and gives what the write
command printed.

After filing, stop: no options panel and no offer of a next step. Reply
in this shape, as plain text outside any code fence, with plain bullets,
no bold (never `- **Label:** ...`), and no local paths:

```text
Filed as WIDGET-91, a Jira work item: https://example.atlassian.net/browse/WIDGET-91

## Unverified

- Repro steps: not provided.
```

The hero line holds the key, the provider's noun, and the URL when there
is one. The reply is that line and, when items still apply, `## Unverified`.
Any prose between them is wrong, including the title, a summary of the
body, the duplicate search, and a readback that matched: the key and URL
in the hero line already come from the readback.

## Rules

- No tracker or repository writes until the filing gate. No commits, no
  pushes, no edits to existing items.
- Never invent a version, an error string, a line number, a link, a
  reference syntax, a reproduction step, an inference about scope,
  cause, or impact, or an Expected or Actual the reporter did not state.
  Missing repro goes under Unverified as "Repro steps: not provided".
  Unverified goes in marked unverified, or comes out.
- Never synthesize a hierarchy level the provider does not have.
