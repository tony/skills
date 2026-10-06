# PR Template Resolution

Procedure for skills that draft a PR description from scratch (`/pr` and
`/pr:rewrite`). `/pr:refresh` never resolves templates; it keeps the
existing structure and does not discuss templates at all.

## Precedence

1. **Template named in the user's message.** When the message or
   argument names a template (a file path, a repo-relative path, or a
   URL), read it and use it. It wins over everything below with no
   question. When the named path does not exist, ask the user to correct
   it; never fall back silently.

2. **Repository template.** Search these locations, case-insensitively:
   - `.github/pull_request_template.md`
   - `pull_request_template.md` (repo root)
   - `docs/pull_request_template.md`
   - `.github/PULL_REQUEST_TEMPLATE/*.md` (multi-template directory)

3. **No template.** Use the section patterns in `/pr` (`../skills/pr/SKILL.md`,
   step 3). Do not mention templates to the user.

## When to ask

Ask through `AskUserQuestion`, never guess, when:

- The multi-template directory holds more than one template and the
  message does not say which applies.
- Templates in more than one standard location differ.
- The user's mention is ambiguous (a name that matches several files).

Offer the candidates as options, plus the `/pr` section patterns.

## Blending

A template supplies the structure: its sections, order, and headings
stay verbatim, including HTML comments and checklists. The `/pr` patterns
(bold impact labels, tables, verification commands, proportionality) fill
the content inside that structure. Add a section the template lacks only
when the diff clearly warrants it, and say so when presenting the draft.
