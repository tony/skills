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
1. **Detect framework**: Scans extensions to determine attribute names
   (`className` vs `class`) and globs.
2. **Structural audit**: Creates a spacing map of mechanisms acting on
   the element group.
3. **Classify anti-patterns**: Matches the catalog's patterns (fragmentation,
   margin/gap mixing, padding asymmetry, fixed widths, wrapper nesting,
   hit targets, space-*/gap collisions), each with a detect command.
4. **Refactor**: Merges fragmented containers, assigns one spacing
   authority, and flattens wrappers.
5. **Validate**: Re-evaluates the spacing map to confirm uniform
   envelopes and authorities.

## Framework Support

| Framework | File extensions | Attribute |
|-----------|----------------|-----------|
| React | `.tsx`, `.jsx` | `className` |
| Vue | `.vue` | `class`, `:class` |
| Svelte | `.svelte` | `class` |
| Astro | `.astro` | `class` |
| HTML | `.html` | `class` |
| Rails (ERB) | `.erb` | `class` |
| Laravel (Blade) | `.blade.php` | `class` |

## Arguments

Target specific files or components:

```console
/tailwind:spacing-audit src/components/TopNav.tsx
```

```console
/tailwind:spacing-audit src/layouts/
```

## Prerequisites

- A project using **Tailwind CSS** v3 or v4; the skill reads the installed
  version and branches Pattern 7 on it
- `rg` (ripgrep) for the detect commands; without it the skill reads files
- Template files in any supported framework
