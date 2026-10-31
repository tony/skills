# tailwind

Detect and fix inconsistent spacing, margin/gap mixing, and padding
asymmetry in Tailwind CSS layouts.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install tailwind --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

`spacing-audit` (`/tailwind:spacing-audit` in Claude Code,
`tailwind:spacing-audit` in Codex) detects and fixes inconsistent spacing
in Tailwind CSS layouts. It finds candidates with `scripts/detect.py`,
falls back to `rg`, then to reading files. See
[`SKILL.md`](skills/spacing-audit/SKILL.md) for the steps.

Step 0 of `SKILL.md` lists the supported template files.

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
  version and adjusts `space-x`/`space-y` advice for it
- `python3` (3.14 or newer) for the detect script; without it the skill falls back to `rg`
  (ripgrep), then to reading files
- Template files in any supported framework
