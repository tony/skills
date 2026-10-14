# Spacing anti-pattern catalog

Each pattern has a signal, a detect command, a before and after, and
when to leave it alone. Examples use `className`; Vue, Svelte, Astro,
HTML, ERB, and Blade use `class`. Physical margins (`ml-*`, `mr-*`) and
logical margins (`ms-*`, `me-*`, added in
[Tailwind v3.3](https://github.com/tailwindlabs/tailwindcss/releases/tag/v3.3.0))
are the same anti-pattern.

## Contents

- Detect command limits
- Container fragmentation
- Margin and gap mixing
- Padding asymmetry
- Fixed width on content-sized items
- Wrapper nesting
- Hit target inconsistency
- space-x and space-y with gap
- Decision tree

## Detect command limits

Each pattern's command is `python3 <absolute path to detect.py> <name> <path>`,
run from the project root; `<path>` is the target from `$ARGUMENTS`,
relative to the project and quoted when it holds spaces. It prints
`path:line:text` for each hit, exits 1 when there is none, and exits 2
when a path does not exist. Needs `python3`. If it cannot run, use the
`rg` fallback under the pattern. The scan skips `node_modules`, `.git`,
`dist`, `build`, `.next`, `.nuxt`, and `vendor` below `<path>`.

`python3 <absolute path to detect.py> version <project root>` prints the
Tailwind major version and the file it came from, or `version: unknown`
with exit 1. A `tailwind.config.*` file is not a signal: v4 loads one
through
[`@config`](https://tailwindcss.com/docs/functions-and-directives#config-directive).

The commands are candidate finders, not proof. They search class tokens
in single, double, and backtick strings, so `class='...'`, `cn("...")`,
`clsx(...)`, and template literals match. `interactive` and `wrapper` match
tags split over several lines.

They cannot see:

- classes assembled at runtime (`` `gap-${n}` ``), `@apply`, `cva`
  variants, and component-library props
- tags whose opening line holds `>` inside an attribute other than
  `=>`, such as a generic `<Foo<T>>`
- files outside the template extensions the script scans
- containers: `vmargin` and `margin-in-gap` match per file, so a
  `flex-col` or `grid` anywhere in a file makes every `mt-*`, `mb-*`,
  and `my-*` in it a hit, and a `gap-*` anywhere pairs with every margin
- vertical margins in a file with no `flex-col` or `grid` (block flow
  collapses them; `margin` never lists `mt-*`, `mb-*`, or `my-*`)
- `mt-auto`, `mx-auto`, and the other `auto` margins, which push instead
  of space
- `space-*` combined with `gap-*` across separate `cn()` arguments
  (`space`, under space-x and space-y with gap, lists them all)

Zero hits is not proof of a clean file. When a command returns nothing
for a file the user named, read that file and apply the pattern by eye.
Every hit needs a read in context.

## Container fragmentation

Items that read as one row are split across sibling containers, each
with its own spacing rule. No `rg` pattern finds this; walk the DOM.

Detect: list the visual peers, then check that all share one flex or
grid parent. The command lists every all-sides and horizontal margin
(`m-`, `ml-`, `mr-`, `ms-`, `me-`, `mx-` with a number or arbitrary
value; `auto` is skipped; vertical margins are `vmargin`, under
Margin and gap mixing). It has no sibling logic; walk the DOM to see which margins
compensate for a split.

```console
$ python3 <absolute path to detect.py> \
    margin \
    <path>
```

Fallback if the script cannot run:

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])-?m[xesrl]?-(?:[0-9\[]|\(--|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
```

Before:

```tsx
<div className="flex items-center gap-1">
  <a href="/profile">Profile</a>
  <button>Billing</button>
</div>

<div className="flex items-center">
  <button>Theme</button>
</div>
```

The Billing to Theme gap comes from the outer parent, not from the
row's `gap-1`, so it differs from the Profile to Billing gap.

After:

```tsx
<div className="flex items-center gap-1">
  <a href="/profile">Profile</a>
  <button>Billing</button>
  <button>Theme</button>
</div>
```

One container, one `gap-1`. Pick the gap value you want the whole row
to have.

## Margin and gap mixing

A flex or grid parent sets `gap-*`, and some children also carry
margin. The margin adds to the gap on that edge.

Detect: list margins in files that also set `gap-*`. All-sides and horizontal margins
always count; `mt-*`, `mb-*`, and `my-*` count when the file has
`flex-col` or `grid`. `auto` margins are skipped because they push
instead of spacing peers. The command stops after 50 hits; narrow the
path and rerun when it says so:

```console
$ python3 <absolute path to detect.py> \
    margin-in-gap \
    <path>
```

To list vertical margins without requiring a gap, such as a `flex-col`
stack that spaces rows with `mt-*` alone, run:

```console
$ python3 <absolute path to detect.py> \
    vmargin \
    <path>
```

Fallback if the script cannot run. It lists
every margin; keep the ones in files that also match the `gap` pattern,
and take the first 50 hits per run:

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])-?m[xesrlytb]?-(?:[0-9\[]|\(--|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
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

After, when the user said the wide gap is meant to stay, make it a
visible divider instead of margin arithmetic:

```tsx
<nav className="flex items-center gap-3">
  <a className="px-2" href="/docs">Docs</a>
  <div className="h-5 w-px bg-slate-300" aria-hidden="true" />
  <button className="px-3">Contact</button>
</nav>
```

The divider is a flex item, so `gap-3` puts 12px on each side of it and
the divider adds no margin. Add `mx-*` only to widen the space on both
sides, and then state the new distance.

Leave alone: a margin on the first or last child that insets from the
container edge. `gap-*` does not govern edge space, but padding on the
parent is cleaner.

## Padding asymmetry

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

Fallback if the script cannot run:

```console
$ rg -n \
    -U \
    -o \
    -e '<(?:a|button|Button|Link|NavLink|[A-Z]\w*(?:Button|Link))\s(?:[^>]|=>)*?(?:class|className)=(?:"[^"]*"|\x27[^\x27]*\x27|\{[^}]*\})' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
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

## Fixed width on content-sized items

One item in a flex row has `w-*` while its siblings size to content.
Extra space pools inside it and it reads wider than its peers.

Detect: `w-` followed by a digit, `[`, or `(--`, at the start of a token, so
`min-w-*` and `max-w-*` do not match:

```console
$ python3 <absolute path to detect.py> \
    width \
    <path>
```

Fallback if the script cannot run:

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])w-(?:[0-9\[]|\(--)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
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

## Wrapper nesting

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

Fallback if the script cannot run:

```console
$ rg -n \
    -U \
    -e '<div\s(?:[^>]|=>)*?(?:class|className)=\{?(?:\w+\()?["\x27\x60](?:[^"\x27\x60]*\s)?(?:flex\s(?:[^"\x27\x60]*\s)?items-center|items-center\s(?:[^"\x27\x60]*\s)?flex)(?:\s[^"\x27\x60]*)?["\x27\x60]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
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

## Hit target inconsistency

Peer interactive elements have different `h-*` classes, so clickable
areas differ and items jitter vertically.

Detect: run the `interactive` command from Padding asymmetry, then compare the `h-*` classes of
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

## space-x and space-y with gap

`space-x-*` and `space-y-*` put margin on children, and `gap-*` adds
space between them, so on one container every gap becomes gap plus
margin. The Tailwind docs say the space utilities are not designed for
grids or layouts that wrap
([margin, Limitations](https://tailwindcss.com/docs/margin#limitations)).
The selector depends on the Tailwind version found in Step 0:

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
[Tailwind v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide#space-between-selector),
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

Fallback if the script cannot run:

```console
$ rg -n \
    -U \
    -e '["\x27\x60](?:[^"\x27\x60]*\s)?gap(?:-[xy])?-(?:[0-9\[]|\(--|px\b)[^"\x27\x60]*\sspace-[xy]-(?:[0-9\[]|\(--|px\b)' \
    -e '["\x27\x60](?:[^"\x27\x60]*\s)?space-[xy]-(?:[0-9\[]|\(--|px\b)[^"\x27\x60]*\sgap(?:-[xy])?-(?:[0-9\[]|\(--|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
```

If the utilities sit in different arguments, such as
`cn("flex gap-2", "space-x-3")`, the command misses them. List every
space utility and read the surrounding call:

```console
$ python3 <absolute path to detect.py> \
    space \
    <path>
```

Fallback if the script cannot run:

```console
$ rg -n \
    -e '(?:^|[\s"\x27\x60:!])space-[xy]-(?:[0-9\[]|\(--|px\b)' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,php,twig,njk,hbs,heex,mdx,liquid}' \
    <path>
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

After (keep the `gap-*` already on the container; use a different value
only when the user asked to preserve the old distance):

```tsx
<div className="flex gap-2">
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
+-- Yes --> space-x and space-y with gap. Remove space-*.
+-- No --> Is A in a different container than B?
    +-- Yes --> Container fragmentation. Merge containers.
    +-- No --> Does the parent have gap-*?
        +-- Yes --> Does A or B also have margin?
        |   +-- Yes --> Margin and gap mixing. Remove margin.
        |   +-- No --> Do A and B have different px-*?
        |       +-- Yes --> Padding asymmetry. Standardize.
        |       +-- No --> Does A or B have a fixed w-*?
        |           +-- Yes --> Fixed width. Remove w-*.
        |           +-- No --> Is A or B a single-child wrapper?
        |               +-- Yes --> Wrapper nesting. Flatten.
        |               +-- No --> Do A and B have different h-*?
        |                   +-- Yes --> Hit target inconsistency. Standardize heights.
        |                   +-- No --> Spacing may be correct. Verify visually.
        +-- No --> Is spacing done via margins?
            +-- Yes --> Margin and gap mixing. Add gap-* to the parent, remove margins.
            +-- No --> Check padding, width, wrapper, and height as in the gap branch above.
                If none applies, spacing may be correct. Verify visually.
```
