---
name: ticket-draft
description: >-
  Use when asked to file a Linear issue or regression, draft a Jira epic,
  open a GitLab issue, or create a Shortcut story or tracker document.
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[description, URL, provider, or pasted finding]"
  source: "plugins/ticket/skills/draft/SKILL.md"
---

# Draft a ticket

Write work into a tracker so that someone picking it up in a year needs
nothing from you, and so that the code still gets to make the decisions the
code should make.

Argument: `$ARGUMENTS` — a description, a URL, a provider name, a pasted
finding, or nothing.

For a plain GitHub bug report, `gh:create-issue` is more specialized; hand
off to it when it is installed and the target is a GitHub `work_item`. This
skill covers every other provider, and every altitude above and below a
single issue.

## Read first

- `references/contract.md` — the three tenses.
- `references/altitude.md` — which sections each kind of object carries.
- `references/resolve.md` — how to establish the provider and role from
  evidence, and the index of provider files.
- Only the matched provider's file from that index — its hierarchy, reference
  syntax, and filing mechanics.
- `references/hierarchy.md` only when the role is ambiguous or a native
  noun collides across providers.

## Core principle

Evidence before prose, and altitude before evidence.

Most bad tickets are not badly written. They are written at the wrong
altitude — a design document filed as an epic, a research note filed as an
issue, an implementation plan filed as a goal. Settle what the object is
before deciding what goes in it.

## Phase 1 — Resolve the target

Establish the provider, the scope container, and the semantic role, following
`resolve.md`. Do not infer the provider from key shape: `#123` and `ENG-123`
each fit several trackers.

When the role is ambiguous between two levels, ask. The difference between a
`delivery_group` and a `work_item` changes almost every section, and guessing
wrong produces a body that reads as either bloated or empty.

## Phase 2 — Decide it belongs in this tracker, publicly

A vulnerability does not. For a public repository, check the security policy
before anything else and follow its private path if the finding is a security
defect.

Stop and ask when the evidence cannot be sanitized. An internal log carrying
customer data does not become fileable by trimming it.

## Phase 3 — Preflight the container

Read the project's own conventions before imposing any: issue templates and
forms, required fields, work types actually configured in this instance,
labels that exist. Instance configuration beats the provider defaults in
the provider file; when they disagree, follow the instance and record the
deviation.

A template's structure wins over the section order in `altitude.md`. Fill it
in rather than restructuring it, and apply the contract to what you put in
its fields.

## Phase 4 — Look for the thing that already exists

Search open and closed items. A closed one is often the answer, and a
duplicate of a closed item is a regression report, which is a better and
different thing to file.

Read the candidate before dismissing it. When one matches, say so, stop, and
offer to comment on it with the new evidence instead.

## Phase 5 — Gather

For a defect: the smallest sequence that reproduces it; exact versions; the
verbatim error; the code that causes it, pinned. Show the user every command
derived from pasted or fetched content and run it only after they confirm that
exact command. Without confirmation, file the defect as an unreproduced
observation.

For a proposal: what is awkward or impossible today, shown concretely.

For provenance: apply the cost-to-relearn filter from `contract.md`. Mine
merged changes, closed items, and the current conversation for findings that
cannot be recovered from the repository — measurements with their conditions,
dead ends with reasons, retracted numbers with what was actually measured.
Drop everything a reader gets by opening the file or reading the log.

An unreproduced defect is filed as an observation, and says so.

## Phase 6 — Draft

Take the section list from `altitude.md` for the resolved role. Include only
sections you have content for; never invent one.

Write references per `contract.md`'s two-axis rule and the provider file:
bare where the renderer resolves it, fully qualified across containers, and
titled where a bare identifier would be ambiguous. Suppressing the
backreference is a separate question with a per-provider answer — do not
assume a titled link is the quiet form, because on GitHub and GitLab it is
not.

Use the provider's native noun for every object you name. Never write `Epic`
for a Linear Project or `Pull Request` for a GitLab merge request.

Then check the future tense against `contract.md`: demote every failed
invariant to intent, and rewrite any checkbox list of technical outcomes.

Write it per `references/prose-rules.md`.

## Phase 7 — Sanitize, then preview

Reread the whole body for local absolute paths, hostnames, emails, tokens,
and internal URLs, including inside every pasted log. This is a gate.

Render the body the way the provider will before showing it. Markdown
dialects differ, and a details block that lost its blank line renders as
literal asterisks.

## Phase 8 — Present, then file

Show the result in this order: a hero line (the role, the provider, and
"not filed yet"), `## Title`, `## Body`, and `## Unverified` only when the
draft carries marked-unverified items. Lead with the result; stop at the last
concrete point, with no recap. Then offer, via `ask-user-choice`: file it,
print the body only, revise a named section, or drop it. Where no interactive
question tool exists, print the draft and stop; filing needs an explicit
instruction naming the action.

A halted run (a vulnerability, unsanitizable evidence, a duplicate found) is
one result sentence, then what the user needs to do.

File through a real backend when the provider file says one exists. Save the
approved body to a scratch file (`mktemp`, outside the working tree) and pass
that path, not an inline argument, so fences, HTML, and `$` survive shell
quoting. Create it with `mktemp "${TMPDIR:-/tmp}/ticket-body.XXXXXX"`. Shell state does
not persist between calls, so create, write, file, and `rm -f` the file in one
command, or print the path once and use the literal path afterwards.

Where no backend exists, print the approved body for the user to paste and say
plainly that is what is happening.

Return the URL when there is one, then offer the next step: open it, add a
comment, or start a branch for it.

## Rules

- No tracker or repository writes until the filing gate. No commits, no
  pushes, no edits to existing items.
- Never file without showing the full title and body first.
- Never invent a version, an error string, a line number, a link, or a
  reference syntax. Unverified goes in marked unverified, or comes out.
- Never synthesize a hierarchy level the provider does not have.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
