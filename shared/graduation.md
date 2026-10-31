# Graduating prereleases to a final

A final cut after its own prereleases (`0.1.1-alpha.2` then `0.1.1`, `0.1.9a1`
then `0.1.9`, `1.0.0-rc.1` then `1.0.0`) gets one changelog section: the net
change since the previous final. It replaces the prerelease sections, whose
tags keep that history. Concatenating them is wrong, because entries within
one cycle cancel out, contradict each other or go stale.

`../scripts/release_plan.py` resolves from this file's directory; write its
absolute path literally in each command.

## Detect

```console
$ python3 <absolute-release_plan.py> graduation <changelog> \
    --repo <repo> \
    --version <final>
```

Without `--version`, the script names the final whose prereleases head the
changelog, if any. Add `--prefix <tag-prefix>` when the prefix is known.

- `graduation` is true when `version` is a final and `sections` lists its
  prerelease sections, newest first, with their line ranges and anchors.
- `baseline_tag` is the highest final tag below `version`. When `tag_prefix`
  is null, `prefixes` lists the namespaces that match: ask which one and rerun
  with `--prefix`; without a question tool, stop. When only `baseline_tag` is
  null, nothing final shipped before: the section describes what `HEAD` ships,
  and no entry is a fix.
- `links` lists the lines outside those sections that link to their anchors.

## Write the final's section

Read the net change first:

```console
$ git log <baseline-tag>..HEAD
```

```console
$ git diff <baseline-tag>..HEAD
```

The entries of the prerelease sections and of the unreleased section are leads
to check against that diff, never text to copy:

- Drop an entry whose change the net diff does not hold, such as one reverted
  later in the cycle.
- Drop an entry that fixes or alters behaviour that arrived after the
  baseline, and describe the final behaviour in that feature's own entry. A
  fix to a feature an earlier prerelease added folds into the feature's entry.
  A migration note for an API the cycle added goes: nobody upgrading from the
  baseline has code that uses it.
- Write one entry for a surface several prereleases changed, describing its
  final shape.
- Keep a fix only when the baseline shipped the bug.
- Check each remaining entry against the net diff, and add one for each
  user-visible change the diff shows that no entry names.

Shape the section like the file's earlier finals: heading, a lead paragraph
when they open with one, subsection names and order. A lead written for a
prerelease, such as how to install it from a prerelease channel, does not
carry over. Write the entries per `prose-rules.md`.

## Replace the prerelease sections

Afterward the file holds, top to bottom: the unreleased heading with its
placeholder and no entries, the final's section, then the sections older than
the prereleases, unchanged.

- Delete every section in `sections`, and the unreleased entries the final's
  section absorbed.
- At each line in `links`, remove a table-of-contents entry and add one for
  the final's section in the same shape; point any other link at the final's
  anchor.
- Find links from other files with one `-e '#<anchor>'` per removed section:

  ```console
  $ git grep -n -F \
      -e '#<anchor>'
  ```
