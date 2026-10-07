# tailwind

Detect and fix inconsistent spacing, margin/gap mixing, and padding
asymmetry in Tailwind CSS layouts.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install tailwind@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add tailwind@skills
```

Claude Code uses a leading slash (`/tailwind:…`). Codex omits it (`tailwind:…`).

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Spacing Audit | `/tailwind:spacing-audit` | `tailwind:spacing-audit` | Detect and fix inconsistent spacing in Tailwind CSS layouts |

## How It Works

The spacing audit follows five steps:

1. Detect the framework and Tailwind version from file extensions and the
   lockfile.
2. Draw a spacing map of the mechanisms acting on the element group.
3. Match the catalog's patterns (fragmentation, margin/gap mixing,
   padding asymmetry, fixed widths, wrapper nesting, hit targets,
   space-*/gap collisions). `scripts/detect.py` finds candidates for each.
4. Merge fragmented containers, assign one spacing authority, and
   flatten wrappers.
5. Redraw the map to confirm uniform envelopes and authorities.

The supported template files are `.tsx` and `.jsx` (`className`), `.vue`
(`class`, `:class`), and `.svelte`, `.astro`, `.html`, `.erb`, and
`.blade.php` (`class`).

## Arguments

Target specific files or components:

```text
/tailwind:spacing-audit src/components/TopNav.tsx
```

```text
/tailwind:spacing-audit src/layouts/
```

## Prerequisites

- A project using **Tailwind CSS** v3 or v4; the skill reads the installed
  version and branches Pattern 7 on it
- `python3` for the detect script; without it the skill falls back to `rg`
  (ripgrep), then to reading files
- Template files in any supported framework
