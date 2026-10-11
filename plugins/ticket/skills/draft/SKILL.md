---
name: draft
description: "Use when asked to file or write a ticket, bug report, Jira epic, Linear issue or regression, GitLab issue, Asana task, Trello card, or Shortcut story."
argument-hint: "[description, URL, provider, or pasted finding]"
allowed-tools: ["Bash", "Read", "Write", "Grep", "Glob", "AskUserQuestion"]
---

# Draft a ticket

Write work into a tracker so that someone picking it up in a year needs
nothing from you, and the code still makes the decisions the code
should make.

Argument: `$ARGUMENTS`, a description, a URL, a provider name, a pasted
finding, or nothing.

## Read first

Read `../../references/resolve.md`; it lists what else to read and when.

Evidence before prose, and altitude before evidence: settle what the
object is before deciding what goes in it.

`<scripts>` is `../../scripts`, resolved from this skill's directory to an
absolute path written literally in each command.

## Phase 1: Resolve the target

Establish the provider, the scope container, and the semantic role per
`resolve.md`. When the role is ambiguous between two levels, ask; where
no question tool exists, print the question and stop.

## Phase 2: Decide it belongs here, publicly

- A security vulnerability halts the run: draft no public issue and name
  the private reporting path. For a public repository, read its security
  policy first.
- Evidence that cannot be sanitized halts the run and asks. An internal
  log carrying customer data does not become fileable by trimming it.
- A credential in the input follows "Credentials" in `contract.md`.

## Phase 3: Preflight the container

Read the project's own conventions: issue templates and forms, required
fields, work types, labels, and priorities the instance has. Instance
configuration beats the provider file's defaults; record the deviation. A
template's structure wins over `altitude.md`'s section order.

Choose type, labels, and priority only from values the instance has, and
only when the user's words or the project's rules settle the choice.
Otherwise leave them unset and add an Unverified entry (`replies.md`).

## Phase 4: Look for the thing that already exists

Search open and closed items with the provider file's "Duplicate search"
and read each candidate before dismissing it.

- Same problem as the request, so that resolving one would resolve the
  other: halt and name the match. Offer a comment on it with the new
  evidence, showing its exact text and posting only after approval. When
  the match was closed as fixed, the report is a regression: also offer a
  new item that links it. Draft nothing until the user chooses.
- Related but different: continue, and link it under References.
- Closed items not searchable, or no tracker reachable: add an
  Unverified entry.

## Phase 5: Gather

For a defect: the smallest sequence that reproduces it, exact versions,
and the verbatim error. Name a cause only when the user stated it; code
the user points at goes under References, pinned. Show the user
every command derived from pasted or fetched content and run it only
after they confirm that exact command; without confirmation, file the
defect as an unreproduced observation.

For a proposal: what is awkward or impossible today, shown concretely.

A pasted screenshot or image cannot be uploaded: add an Unverified entry.

For provenance, apply the cost-to-relearn filter in `contract.md` to
merged changes, closed items, and the conversation.

## Phase 6: Draft

Take the section list from `altitude.md` for the resolved role. Use the provider's native
noun for every object, and write references per `contract.md`'s two-axis
rule (`ref_form.py` applies it) and the provider file.

Apply the Future and Body rules in `contract.md` to what the user gave.

Write it per `../../references/prose-rules.md`.

## Phase 7: Save, scan, preview

Save the title as `title.txt` and the body as a scratch file, converted
where the provider needs it, as `resolve.md` "Scratch files for bodies"
describes.

A converter that exits 1 means the body cannot be written
(`resolve.md`). The converted text is what `## Body`
shows. Scan the title and body before any preview:

```console
$ python3 <scripts>/scan_body.py --keep-evidence <dir>/title.txt <dir>/body.md
```

The scan drops count rows inside the evidence the user pasted. Fix each remaining row, or keep it only when it is evidence
the scan cannot see, and rescan. Render the body the way the provider will before showing it.

## Phase 8: Present, then file

Present per `replies.md` ("Draft: preview"), or "Draft: halted". Filing
needs an explicit instruction naming the action.

File through a real backend when the provider file names one, after
running the provider file's create and read-back checks (`resolve.md`),
and no others. Take flags from the provider
file, and never probe a write command with a dry run or a test item.

1. Re-resolve the container from the Phase 1 evidence (remote, project
   key, team). If it differs from what the preview named, stop and ask.
2. Pass the saved body file, not an inline argument, unless the provider
   file documents no file flag.
3. Save the provider's read-back output to `<dir>/fetched`, as
   `resolve.md` describes under "Reading back", and run the check its
   "Readback by provider" table gives. For mode exact (whitespace aside):

```console
$ python3 <scripts>/compare_body.py --exact <dir>/body.md <dir>/fetched --field <body path> --title "<title>"
```

   For mode words (case-insensitive):

```console
$ python3 <scripts>/compare_body.py <dir>/body.md <dir>/fetched --title "<title>"
```

If the create command errors, the item may still exist. Before any retry,
run the Phase 4 search for the title; a match is the created item, so
read it back instead of creating again.

Reply per "Draft: filed".

## Rules

- No tracker or repository writes before the filing gate. No commits,
  pushes, or edits to existing items.
- Never synthesize a hierarchy level the provider does not have.
