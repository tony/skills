---
type: regex
target: last_message
pattern: '^[^\n]+\n\n## Ledger\n\n- (?!\*\*)(?![\s\S]*\n- \*\*)(?:(?!\n## )[\s\S])*\n## Behavior changes\n\n- (?:(?!\n## )[\s\S])*\n## Diff\n\n```diff\n(?!```)(?:(?!\n```)[\s\S])*\n```\s*$'
---
