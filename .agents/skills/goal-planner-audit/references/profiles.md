# Profiles and machine bindings

A profile holds explicitly approved planning defaults. Write proposed values
and their rationale under [prose-rules.md](./prose-rules.md). Keep the profile
small enough to inspect before adopting it.

## Contents

- Separate three kinds of input
- Select and approve
- Persist and transfer

## Separate three kinds of input

Portable preferences can select evidence standards, prose rules, independent
review triggers, resource-policy principles, host/output defaults, and optional
integrations. They cannot override the instruction hierarchy or grant future
publication authority.

Project context supplies target identity, language/framework conventions,
quality commands, compatibility rules, task-specific exceptions, and delivery
requirements. Re-read it for the current target rather than copying it into
universal defaults.

Store the chosen Documents root in a separate machine binding. Discover
workspace roots, installed tools, available reviewers, resource probes, and
owned scratch/build locations when needed; they are not profile defaults.
Native and mounted Documents roots remain distinct;
never infer a username or equate directories because both are called Documents.

## Select and approve

An explicit request to save named values is approval for those values. Preserve
earlier approval in the same session. History can suggest sourced candidate
defaults, but cannot silently promote them, change memory, or rewrite local
configuration. Show unselected candidates and await the user's selection
before persistence. Treat one-off release permissions, model names, platform
exclusions, timing holds, machine thresholds, and paths as scoped until the
user deliberately promotes an appropriate default.

For history-derived candidates use [recovery.md](./recovery.md). Prefer direct
user evidence; retain contradictions and origin limits. Never claim that a
profile represents every historical preference or turn an assistant's habit
into the user's rule. No history available is a recovery gap, not a reason
to invent a preference.

## Persist and transfer

Use `planner.py` profile and binding validation before persistence. The
helper is `./planner.py`, resolved from this reference's directory to
an absolute path written literally in every command. Skills declare their own
relative path to this helper.

A profile uses this strict JSON schema. Set `approved: true` only for values
the user has selected. `max_chars` is optional; omit it for uncapped Codex
drafting. Claude profile limits cannot spend the user-addendum reserve.

```json
{
  "schema_version": 1,
  "kind": "profile",
  "approved": true,
  "name": "portable",
  "defaults": {"host": "claude", "save": true, "max_chars": 3800},
  "principles": ["Require independent review for delivery goals."]
}
```

The separate binding schema requires an absolute Documents path or a path
starting with `~/`, so a saved binding is independent of the working directory:

```json
{
  "schema_version": 1,
  "kind": "bindings",
  "approved": true,
  "documents_root": "~/Documents"
}
```

Read and validate a selected profile:

```console
$ python3 <planner> profile read \
    --path <profile.json>
```

Persist an approved profile, substituting the actual selected values:

```console
$ python3 <planner> profile write \
    --input - \
    --path <profile.json> \
    --approved <<'JSON'
{"schema_version":1,"kind":"profile","approved":true,"name":"portable","defaults":{"host":"claude","save":true,"max_chars":3800},"principles":[]}
JSON
```

Use `bindings read` and `bindings write` with the same options and the bindings
schema for the selected Documents root. Read back the saved file to compare it
with the approved values. No automatic profile discovery or application occurs;
the calling skill supplies selected defaults to rendering explicitly.

Use a user-selected file location. A new-file write must not overwrite an
existing file. Replacing an existing profile requires the user's approved
revision of those values, followed by read-back validation. A CLI approval
flag records existing authorization; passing it cannot manufacture consent.
Print the whole proposed/saved values and persistence result using
[output.md](./output.md).

Transfer approved preferences by the user's chosen file or repository
mechanism. Never upload histories implicitly. Exclude transcripts, credentials,
private paths, and private marketplace dependencies from the portable profile.
Resolve bindings on the receiving machine; missing tools remain unavailable
or UNVERIFIED when required. Do not pretend a path or provider exists.

When moving a goal bundle, verify companion hashes and identities. Reconcile
changed contracts before trusting a launcher, and render a new numbered goal
when its machine-specific locator changes. Profile transfer does not activate
any goal or import old execution permissions.
