# Unknown or unsupported tracker

Fallback for a tracker with no file of its own — an internal system, a
self-hosted forge, a spreadsheet someone calls a backlog.

## Scope

Unknown. Ask, or read it from the artifact you were given. Do not assume a
containment chain exists at all; some systems are a flat list.

## Native hierarchy

Establish it from evidence rather than assuming one. Ask two questions:

- Does this system have an object *larger* than an ordinary work item, and is
  it native or a naming convention?
- Does it have an object *smaller* than one, and can that smaller object
  exist independently?

Answers give you `delivery_group`, `work_item`, and `sub_item`. Everything
else is optional and probably absent.

When the answer is unclear, treat the system as having exactly one authored
level — `work_item` — and record `mapping_basis: convention` for anything
someone calls an epic or a project.

## Semantic roles

Map what you can observe, and record what you cannot as `absent` rather than
inferring it. A tracker that has never shown you an initiative does not have
one.

Keep support status and requirement separate even here. "This system has no
epic" and "this system does not require an epic" are different facts, and
guessing the second from the first is how a convention becomes a mandate.

## Orthogonal objects

Assume none exist until observed. In particular, do not read a status column,
a swimlane, a tag, or a folder as a parent. Those are `visualized_by` or
`grouped_by` at most.

## References and autolinks

Assume nothing is auto-detected. Write every reference as an explicit titled
link with a full URL.

This is the safe default in both directions: an explicit link renders
correctly in every markdown dialect, and it does not mint a backreference in
a system whose side effects you have not verified.

If the user tells you the system auto-detects a form, use it and record that
you were told rather than that you verified it.

Do not carry another provider's syntax across. A bare `#123` in an unknown
tracker is either a dead reference or a link to the wrong thing.

## Reading and writing

Assume no backend. Draft, render, present the full title and body, and emit
the approved text for the user to paste. Say plainly that is what is
happening rather than implying something was filed.

Where the user names a CLI or API, confirm the exact invocation with them
before running it. An unverified write path against an unknown tracker is
worth one question.

## Naming traps

Use the nouns the user uses, and mirror them back exactly. When their noun
collides with a loaded one from `hierarchy.md`, qualify it once on first use
and then keep their word.

Never introduce `Epic`, `Initiative`, `Sprint`, or `Milestone` into a system
that does not use them. Naming a thing creates the expectation that the
system has it.
