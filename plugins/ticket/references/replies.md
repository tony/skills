# Reply shapes

Contents: Shared form; Unverified entries; Restricted options; Draft: preview; Draft: halted; Draft: filed; Rebuild: preview; Rebuild: updated.

## Shared form

Reply as plain text outside any code fence, with plain bullets, no bold
labels, no tables, and no local paths. The reply is
the shape filled in: nothing before its first line, nothing after its
last. Stop at the last concrete point, with no recap, "Next step" line,
comment on the draft's strength, or free-prose offer or question.

Explain each change in the user's terms, from the request's own wording.
Never cite the skill's rules, predict consequences, or claim anything
about the project's state or the work's success.

Name tools as the user knows them
(`glab`), never as a stub, fixture, or sandbox. An Unverified item never
says a thing was or will be filed.

Where no question tool exists, print the result, list the options as
plain bullets, and stop. Name the action to reply with ("Reply 'file
it'"), not the missing tool.

## Unverified entries

Unverified is the one place for what the run could not settle; `contract.md` says
when an entry is required. The wording is fixed, and an entry never says a thing
was or will be filed:

- "Invariants: none stated"
- "Repro steps: not provided"
- "Design document: none linked"
- "Labels: not chosen" (or the field name)
- "Closed items not searched"
- "Duplicate check not run"
- "Screenshot: attach manually"
- "Readback: not verified"
- "<provider default>: not confirmed"

## Restricted options

Print the body, revise, and drop it. `resolve.md` says when they apply.

## Draft: preview

Order: a hero line, `## Title`, `## Body`, `## Changed from your
request`, `## Unverified`, then the options.

- The hero line is at most 25 words: the role, the provider, and "not
  filed yet". Name a role even for a plain issue ("work item"). It holds
  no reasons, backend, Team, or reproduction status, and never opens with
  "Below is" or "Here is".
- `## Changed from your request` appears only when you altered something
  the user asked for or redacted something they pasted.
- `## Unverified` appears only when the draft carries unverified items.

Options via `AskUserQuestion`: file it, print the body only, revise, or
drop it. Revise is open: the user names a section or states any change,
including a detail to add.

```text
<Provider noun> (<role>), not filed yet.

## Title

<outcome-stating title>

## Body

<the full body, as it will render in the provider>

## Changed from your request

- "<the user's phrase>" is now Intent, as a non-binding choice.

## Unverified

- <what the draft could not verify, and why>.

Should I file it, print the body by itself, revise it, or drop it?
```

## Draft: halted

A halted run (a vulnerability, unsanitizable evidence, a duplicate) is
one result sentence starting "Halted:", then what the user must do as
plain bullets, with no second paragraph, no speculation about causes, and
no draft. A duplicate names the match in that sentence.

```text
Halted: this looks like a security vulnerability, so no public issue
was drafted.

- Report it through the repository's private vulnerability reporting.
- Share details only through that channel.
```

## Draft: filed

After filing, stop: no options and no next-step offer. The reply is the
hero line, then `## Unverified` when items still apply. Any prose between
them is wrong, including the title, a summary of the body, the duplicate
search, and a matched readback. Take the key, URL, and title from the
readback.

On a failed readback the hero line says `Filed, readback failed:` or
`Filed as KEY: URL, but it reads back differently.`, then the first
mismatch line and what the write command printed.

```text
Filed as <KEY>, a <provider noun>: <URL>

## Unverified

- <what still applies>.
```

## Rebuild: preview

Order: a hero line, then `## Kept`, `## Cut`, `## Relocated`,
`## Demoted`, `## Missing`, `## Rebuilt title and body`, then the options.

- The hero line is one line: the role it is and the role it should be,
  or what was wrong with it when the role stands. No bucket counts. The
  next line says what you could not see (work type, comments).
- Kept: what survived, and why each item could not be re-derived.
- Cut: every dropped item quoted in its original words, grouped by
  reason, so the user can veto any. Include process gates.
- Relocated: what moved and where, with the new document's title and
  full text.
- Demoted: each old definition-of-done item and what it became. A Cut
  item never appears here, and a missing invariant belongs under Missing.
- Missing: what the item never had.

Options via `AskUserQuestion`, and no others:

- Update the item. Relocated content with no document created stays in
  the body.
- Create the document, then update the item. Offered only when content
  was relocated.
- Print the body only.
- Revise. Open: the user names a section or states any change; when
  Missing holds one fact the user could state in a sentence, the option
  asks for it.
- Drop it.

A halted run (no readable item, unsanitizable evidence) is one result
sentence, then what the user must do.

```text
<KEY> is a <provider noun> written as <what it was>; rebuilt as a <role>.
<What could not be seen, such as comments or work type.>

## Kept

- <item>: <why it cannot be re-derived>.

## Cut

- "<original text>": <why the repository or the diff holds it>.

## Relocated

- Nothing.

## Demoted

- "<original item>" becomes Intent, as a non-binding choice.

## Missing

- <what the item never had>.

## Rebuilt title and body

<the full title and body>
```

## Rebuild: updated

After a successful update, the reply is a hero line with the URL and the
readback result, then
`## Original body` holding the replaced body in a `text` fence, redacted per "Credentials" in `contract.md`. The scratch
copy is deleted after this reply, so this is the only record the user keeps.

```text
Updated <KEY>: <URL>. Read back: body and title matched.

## Original body

<the replaced body>
```
