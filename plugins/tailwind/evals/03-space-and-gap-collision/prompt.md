---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
The tags in this Tailwind v4 component are spaced much wider than I wanted. Fix the spacing:

```tsx
<div className="flex gap-2 space-x-3">
  <span>Tag 1</span>
  <span>Tag 2</span>
  <span>Tag 3</span>
</div>
```
