# tailwind

Detect and fix inconsistent spacing, margin/gap mixing, and padding
asymmetry in Tailwind CSS layouts.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install tailwind@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add tailwind@skills
```

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Tailwind Spacing Audit | `/tailwind:spacing-audit` | `tailwind:spacing-audit` | Systematically detect and fix inconsistent spacing in Tailwind CSS v4+ layouts |

## How It Works

The spacing audit follows a 5-step workflow:
1. **Detect framework**: Scans extensions to determine attribute names
   (`className` vs `class`) and globs.
2. **Structural audit**: Creates a spacing map of mechanisms acting on
   the element group.
3. **Classify anti-patterns**: Matches against seven heuristics
   (fragmentation, margin/gap mixing, padding asymmetry, wrapper
   nesting, etc.).
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

- A project using **Tailwind CSS** (v4+ recommended, v3 supported)
- Template files in any supported framework
