# Spacing anti-pattern catalog

Seven patterns, ordered by how often they cause visible unevenness. Each
has a signal, a detect command, a before and after, and when to leave it
alone. Examples use `className`; Vue, Svelte, Astro, HTML, ERB, and Blade
use `class`. Physical margins (`ml-*`, `mr-*`) and logical margins
(`ms-*`, `me-*`) are the same anti-pattern.

Detect commands match both attributes in every supported template
extension. Each hit needs a read in context.

## Contents

- Pattern 1: Container fragmentation
- Pattern 2: Margin and gap mixing
- Pattern 3: Padding asymmetry
- Pattern 4: Fixed width on content-sized items
- Pattern 5: Wrapper nesting
- Pattern 6: Hit target inconsistency
- Pattern 7: space-x and space-y with gap
- Decision tree

## Pattern 1: Container fragmentation

Items that read as one row are split across sibling containers, each
with its own spacing rule. No `rg` pattern finds this; walk the DOM.

Detect: list the visual peers, then check that all share one flex or
grid parent. Margins on a container that has a flex sibling hint at it:

```console
$ rg -n \
    '(class|className)=[^>]*[ "'"'"':]-?m[esrlx]-[0-9]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

Before:

```tsx
<div className="me-1 flex gap-1">
  <a className="flex h-12 items-center" href="/social">
    <img className="h-6 w-auto" alt="Social" src="..." />
  </a>
  <button className="flex h-12 items-center px-2">
    <WrenchIcon className="h-5 w-5" />
  </button>
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>B</span><span>Babylon.js</span>
  </button>
</div>

<div className="me-2 flex place-items-center">
  <button className="flex h-8 w-24 items-center gap-1.5 rounded px-2">
    <span>Theme</span>
  </button>
</div>
```

The Wrench to Babylon.js gap is `gap-1`. The Babylon.js to Theme gap is
`me-1` plus whatever the outer parent adds. They differ.

After:

```tsx
<div className="flex items-center gap-2">
  <a className="flex h-12 items-center px-2" href="/social">
    <img className="h-6 w-auto" alt="Social" src="..." />
  </a>
  <button className="flex h-12 items-center px-2">
    <WrenchIcon className="h-5 w-5" />
  </button>
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>B</span><span>Babylon.js</span>
  </button>
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>Theme</span>
  </button>
</div>
```

One container, one `gap-2`. The `me-*` hacks and `w-24` are gone
(Patterns 2 and 4), and the social link gained `px-2` (Pattern 3).

## Pattern 2: Margin and gap mixing

A flex or grid parent sets `gap-*`, and some children also carry
margin. The margin adds to the gap on that edge.

Detect: find parents with gap, then margins on their children:

```console
$ rg -n \
    '(class|className)="[^"]*(flex|grid)[^"]*gap-' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

```console
$ rg -n \
    '(class|className)=[^>]*[ "'"'"':]-?m[trblxyse]?-[0-9a\[ps]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
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
their padding classes, and compare. Candidates:

```console
$ rg -n \
    '<(a|button)[^>]*(class|className)=' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
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

Detect: `w-` followed by a digit, not preceded by `-`, so `min-w-*` and
`max-w-*` do not match:

```console
$ rg -n \
    '(class|className)=[^>]*[ "'"'"':]w-[0-9]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

Before:

```tsx
<div className="flex items-center gap-2">
  <button className="flex h-8 items-center gap-1.5 rounded px-2">
    <span>Babylon.js</span>
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

Detect: divs with flex and `items-center`, then check each for one child:

```console
$ rg -n \
    '<div (class|className)="[^"]*flex[^"]*items-center[^"]*">' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
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

Detect: collect the `h-*` classes of the peers in one container and
compare.

```console
$ rg -n \
    '<(a|button)[^>]*(class|className)=[^>]*[ "'"'"':]h-[0-9]' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

Before:

```tsx
<div className="flex items-center gap-2">
  <a className="flex h-6 items-center">
    <img className="h-6" src="icon.svg" alt="" />
  </a>
  <button className="flex h-12 items-center px-2"><WrenchIcon /></button>
  <button className="flex h-8 items-center px-2"><span>Menu</span></button>
</div>
```

After: every peer uses the bar height (`h-12`) with `items-center`, and
the icon keeps its visual size.

## Pattern 7: space-x and space-y with gap

In Tailwind v4, `space-x-*` and `space-y-*` add margin to every child
except the last (`& > :not(:last-child)`). With `gap-*` on the same
container, every gap becomes gap plus margin. The space utilities also
misbehave with wrapping and grids.

Detect: both utilities in one class list, in either order:

```console
$ rg -n \
    '(class|className)="[^"]*gap-[^"]*space-[xy]-' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

```console
$ rg -n \
    '(class|className)="[^"]*space-[xy]-[^"]*gap-' \
    -g '*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'
```

Before:

```tsx
<div className="flex gap-2 space-x-3">
  <span>Tag 1</span>
  <span>Tag 2</span>
  <span>Tag 3</span>
</div>
```

Every gap is 8 + 12 = 20px, and the margin follows the child, so hiding
or reordering the last child changes the spacing.

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

```
Is A in a different container than B?
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
    |                   +-- No --> Does the parent also have space-*?
    |                       +-- Yes --> Pattern 7. Remove space-*.
    |                       +-- No --> Spacing may be correct. Verify visually.
    +-- No --> Is spacing done via margins?
        +-- Yes --> Add gap-* to parent, remove margins.
```
