# Exempting a package from a cooldown

A cooldown hides releases younger than a threshold from the resolver. An
exemption is a hole in a supply-chain guard, so keep it small and
temporary.

Exempt only when the resolver cannot see a release needed now. Skip it
when the resolver already sees the release or the window is short enough
to wait out; a version the user named does not override the wait.

- Confirm the exemption with the user before writing it. Without a way
  to ask, write nothing and report when the release becomes visible.
- Exempt the one package, never the cooldown globally. Use the
  per-package override the tool documents; a tool with none means waiting.
- Prefer an override form that carries no date. A dated override ages
  into the lockfile and stops meaning anything.
- Annotate it in the file with the reason and the condition for removal.
  A format that rejects comments (JSON) takes the annotation in the
  commit message instead.
- Land it as its own commit, first in the branch, so one revert removes
  it.
- Compute when the block lapses (publication timestamp plus the window),
  state it in the commit body, and revert the exemption then.
- When the work goes through a pull request, name the revert as a
  pre-merge requirement in its body, with the lapse time.
