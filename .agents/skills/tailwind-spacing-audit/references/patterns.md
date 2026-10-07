# Spacing anti-pattern catalog

Each pattern has a signal, a detect command, a before and after, and
when to leave it alone. Examples use `className`; Vue, Svelte, Astro,
HTML, ERB, and Blade use `class`. Physical margins (`ml-*`, `mr-*`) and
logical margins (`ms-*`, `me-*`, added in
[Tailwind v3.3](https://github.com/tailwindlabs/tailwindcss/releases/tag/v3.3.0))
are the same anti-pattern.

## Detect command limits

Each pattern's command is `python3 <absolute path to detect.py> <name> <path>`,
run from the project root; `<path>` is the target from `$ARGUMENTS`,
relative to the project. It prints `path:line:text` for each hit, exits
1 when there is none, and exits 2 when a path does not exist. Needs
`python3`. If it cannot run, use the `rg` fallback
under the pattern.

The commands are candidate finders, not proof. They search class tokens
in single, double, and backtick strings, so `class='...'`, `cn("...")`,
`clsx(...)`, and template literals match. Patterns 3, 5, and 6 match
tags split over several lines.

They cannot see:

- classes assembled at runtime (`` `gap-${n}` ``), `@apply`, `cva`
  variants, and component-library props
- `className` values built across several string arguments (Pattern 7
  has a second command for this)
- tags whose opening line holds `>` inside an attribute other than
  `=>`, such as a generic `<Foo<T>>`
- files outside the template extensions the script scans

Zero hits is not proof of a clean file. When a command returns nothing
for a file the user named, read that file and apply the pattern by eye.
Every hit needs a read in context.

## Contents

- Detect command limits
- Pattern 1: Container fragmentation
- Pattern 2: Margin and gap mixing
- Pattern 3: Padding asymmetry
- Pattern 4: Fixed width on content-sized items
- Pattern 5: Wrapper nesting
- Pattern 6: Hit target inconsistency
- Pattern 7: space-x and space-y with gap (v3 and v4)
- Decision tree

## Pattern 1: Container fragmentation

Items that read as one row are split across sibling containers, each
with its own spacing rule. No `rg` pattern finds this; walk the DOM.

Detect: list the visual peers, then check that all share one flex or
grid parent. The command lists every horizontal margin (`ml-`, `mr-`,
`ms-`, `me-`, `mx-` with a number or arbitrary value; `mx-auto` is
skipped). It has no sibling logic; walk the DOM to see which margins
compensate for a split.

```console
$ python3 <absolute path to detect.py> \
    margin \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])-?m[xesrl]-(?:[0-9\[]|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<div className="me-1 flex gap-1">
  <a className="flex h-12 items-center" href="/profile">
    <img className="h-6 w-auto" alt="Profile" src="..." />
  </a>
  <button className="flex h-12 items-center px-2">
    <SettingsIcon className="h-5 w-5" />
  </button>
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>B</span><span>Billing</span>
  </button>
</div>

<div className="me-2 flex place-items-center">
  <button className="flex h-8 w-24 items-center gap-1.5 rounded px-2">
    <span>Theme</span>
  </button>
</div>
```

The Settings to Billing gap is `gap-1`. The Billing to Theme gap is
`me-1` plus whatever the outer parent adds. They differ.

After:

```tsx
<div className="flex items-center gap-1">
  <a className="flex h-12 items-center px-2" href="/profile">
    <img className="h-6 w-auto" alt="Profile" src="..." />
  </a>
  <button className="flex h-12 items-center px-2">
    <SettingsIcon className="h-5 w-5" />
  </button>
  <button className="flex h-12 items-center gap-1.5 rounded px-2">
    <span>B</span><span>Billing</span>
  </button>
  <button className="flex h-12 items-center gap-1.5 rounded px-2">
    <span>Theme</span>
  </button>
</div>
```

One container, one `gap-1`: the Settings to Billing gap is unchanged,
and the Billing to Theme gap shrinks to match it (it was `me-1` plus
the outer parent's spacing). Pick the gap value you want the whole row
to have. The `me-*` hacks and `w-24` are gone (Patterns 2 and 4), the
profile link gained `px-2` (Pattern 3), and all four peers share `h-12`
(Pattern 6).

## Pattern 2: Margin and gap mixing

A flex or grid parent sets `gap-*`, and some children also carry
margin. The margin adds to the gap on that edge.

Detect: find parents with gap, then margins on their children. A file in
both lists is a candidate:

```console
$ python3 <absolute path to detect.py> \
    gap \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])gap(?:-[xy])?-(?:[0-9\[]|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Then list margins, numeric and arbitrary values. `mx-auto` is skipped
because it centers a block instead of spacing peers:

```console
$ python3 <absolute path to detect.py> \
    margin \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])-?m[xesrl]-(?:[0-9\[]|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<nav className="flex items-center gap-3">
  <a className="px-2" href="/">Home</a>
  <a className="px-2" href="/about">About</a>
  <a className="px-2 me-4" href="/docs">Docs</a>
  <button className="ms-2 px-3">Contact</button>
</nav>
```

Docs to Contact is 12 + 16 + 8 = 36px; every other gap is 12px.

After, uniform:

```tsx
<nav className="flex items-center gap-3">
  <a className="px-2" href="/">Home</a>
  <a className="px-2" href="/about">About</a>
  <a className="px-2" href="/docs">Docs</a>
  <button className="px-3">Contact</button>
</nav>
```

After, if the wide gap was a deliberate break, make it a visible
divider instead of margin arithmetic:

```tsx
<nav className="flex items-center gap-3">
  <a className="px-2" href="/docs">Docs</a>
  <div className="mx-1 h-5 w-px bg-slate-300" aria-hidden="true" />
  <button className="px-3">Contact</button>
</nav>
```

Leave alone: a margin on the first or last child that insets from the
container edge. `gap-*` does not govern edge space, but padding on the
parent is cleaner.

## Pattern 3: Padding asymmetry

Peer interactive elements in one row have different `px-*`, `py-*`, or
`p-*`. Their content sits unevenly even when the gaps match.

Detect: list the buttons, links, and toggles in one container, extract
their padding classes, and compare. The command prints each
interactive element's class attribute, including multi-line tags and
elements with `=>` props. Component names outside the pattern
(`IconButton` matches; `Action` does not) need a read of the file:

```console
$ python3 <absolute path to detect.py> \
    interactive \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -U \
    -o \
    -e '<(?:a|button|Button|Link|NavLink|[A-Z]\w*(?:Button|Link))\s(?:[^>]|=>)*?(?:class|className)=(?:"[^"]*"|\x27[^\x27]*\x27|\{[^}]*\})' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<div className="flex items-center gap-2">
  <a className="flex h-12 items-center" href="/profile">
    <img className="h-6" src="avatar.png" alt="" />
  </a>
  <button className="flex h-12 items-center px-2">
    <SettingsIcon />
  </button>
  <button className="flex h-12 items-center px-4">
    <span>Settings</span>
  </button>
</div>
```

After: all three use `px-2`.

If text-heavy items truly need more padding, they probably belong to a
different visual group.

## Pattern 4: Fixed width on content-sized items

One item in a flex row has `w-*` while its siblings size to content.
Extra space pools inside it and it reads wider than its peers.

Detect: `w-` followed by a digit or `[`, at the start of a token, so
`min-w-*` and `max-w-*` do not match:

```console
$ python3 <absolute path to detect.py> \
    width \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:])w-[0-9\[]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<div className="flex items-center gap-2">
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>Billing</span>
  </button>
  <button className="flex h-8 w-24 items-center gap-1.5 rounded px-2">
    <span>Theme</span>
  </button>
</div>
```

After: remove `w-24`; content and padding set the width.

Leave alone: `min-w-*` and `max-w-*` (they constrain, not fix); grid
cells that must align; form inputs that share a field width; counters
whose text length varies enough to cause layout shift.

## Pattern 5: Wrapper nesting

A single-child `<div>` with flex alignment classes wraps an element that
could take those classes itself. The parent's `gap-*` then acts between
wrappers, whose size differs from their content.

Detect: divs with `flex` and `items-center` in either order (not
`inline-flex`, `flex-col`, or `place-items-center`), then check each for
one child. The command reads the first string inside `cn(...)` or
`clsx(...)` too:

```console
$ python3 <absolute path to detect.py> \
    wrapper \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -U \
    -e '<div\s(?:[^>]|=>)*?(?:class|className)=\{?(?:\w+\()?["\x27\x60](?:[^"\x27\x60]*\s)?(?:flex\s(?:[^"\x27\x60]*\s)?items-center|items-center\s(?:[^"\x27\x60]*\s)?flex)(?:\s[^"\x27\x60]*)?["\x27\x60]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<div className="flex items-center gap-2">
  <div className="flex h-full items-center">
    <button className="flex h-8 items-center gap-1.5 rounded px-2">
      <span>Theme</span>
    </button>
  </div>
</div>
```

After: the button is a direct child of the gap container, and
`items-center` on the parent centers it.

Leave alone: a wrapper that carries padding, background, or border the
child cannot take, and any wrapper around more than one child.

## Pattern 6: Hit target inconsistency

Peer interactive elements have different `h-*` classes, so clickable
areas differ and items jitter vertically.

Detect: run the Pattern 3 command, then compare the `h-*` classes of
the peers in one container.

Before:

```tsx
<div className="flex items-center gap-2">
  <a className="flex h-6 items-center">
    <img className="h-6" src="icon.svg" alt="" />
  </a>
  <button className="flex h-12 items-center px-2"><SettingsIcon /></button>
  <button className="flex h-8 items-center px-2"><span>Menu</span></button>
</div>
```

After: every peer uses the bar height (`h-12`) with `items-center`, and
the icon keeps its visual size.

## Pattern 7: space-x and space-y with gap

`space-x-*` and `space-y-*` put margin on children, and `gap-*` adds
space between them, so on one container every gap becomes gap plus
margin. The space utilities also misbehave with wrapping and grids. The
selector depends on the Tailwind version found in Step 0:

- v4: margin goes on every child except the last
  (`> :not(:last-child)`). Hiding the last child leaves its previous
  sibling's margin behind as trailing space.
- v3: margin goes on every child after the first visible one
  (`> :not([hidden]) ~ :not([hidden])`), and children with the `hidden`
  attribute are skipped.
- Version unknown: state the collision (gap plus margin) and make no
  claim about hidden children.

Selector sources: v4 is the section on the `space-x-*` and `space-y-*`
selector change in the
[Tailwind v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide),
which also recommends migrating to `gap` when the change causes
problems. v3 is the `space` plugin in
[`corePlugins.js` at v3.4.0](https://github.com/tailwindlabs/tailwindcss/blob/v3.4.0/src/corePlugins.js).
The upgrade guide is unversioned; fetch it when the version question
decides the advice.

Detect: both utilities in one string, in either order. The command also
reads template literals and `cn()` strings that hold both:

```console
$ python3 <absolute path to detect.py> \
    space-gap \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -U \
    -e '["\x27\x60](?:[^"\x27\x60]*\s)?gap(?:-[xy])?-[0-9\[][^"\x27\x60]*\sspace-[xy]-[0-9\[]' \
    -e '["\x27\x60](?:[^"\x27\x60]*\s)?space-[xy]-[0-9\[][^"\x27\x60]*\sgap(?:-[xy])?-[0-9\[]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

If the utilities sit in different arguments, such as
`cn("flex gap-2", "space-x-3")`, the command misses them. List every
space utility and read the surrounding call:

```console
$ python3 <absolute path to detect.py> \
    space \
    <path>
```

Fallback if the script cannot run (replace `.` with the target):

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])space-[xy]-(?:[0-9\[]|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}' \
    .
```

Before:

```tsx
<div className="flex gap-2 space-x-3">
  <span>Tag 1</span>
  <span>Tag 2</span>
  <span>Tag 3</span>
</div>
```

Every gap is 8 + 12 = 20px, and the margin follows the child, so
reordering children changes the spacing (in v4, hiding the last child
does too).

After:

```tsx
<div className="flex gap-3">
  <span>Tag 1</span>
  <span>Tag 2</span>
  <span>Tag 3</span>
</div>
```

A lone `space-*` on a container without `gap-*` is not this pattern.
Flag it as a migration opportunity only when the file already uses
`gap-*` elsewhere.

## Decision tree

For a spacing issue between items A and B:

```text
Does the parent have both gap-* and space-*?
+-- Yes --> Pattern 7. Remove space-*.
+-- No --> Is A in a different container than B?
    +-- Yes --> Pattern 1. Merge containers.
    +-- No --> Does the parent have gap-*?
        +-- Yes --> Does A or B also have margin?
        |   +-- Yes --> Pattern 2. Remove margin.
        |   +-- No --> Do A and B have different px-*?
        |       +-- Yes --> Pattern 3. Standardize.
        |       +-- No --> Does A or B have a fixed w-*?
        |           +-- Yes --> Pattern 4. Remove w-*.
        |           +-- No --> Is A or B a single-child wrapper?
        |               +-- Yes --> Pattern 5. Flatten.
        |               +-- No --> Do A and B have different h-*?
        |                   +-- Yes --> Pattern 6. Standardize heights.
        |                   +-- No --> Spacing may be correct. Verify visually.
        +-- No --> Is spacing done via margins?
            +-- Yes --> Pattern 2. Add gap-* to the parent, remove margins.
            +-- No --> Spacing may be correct. Verify visually.
```
