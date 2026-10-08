---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
The gap between Docs and Contact in this Tailwind nav is way bigger than the others. Audit and fix the spacing:

```tsx
<nav className="flex items-center gap-3">
  <a className="px-2" href="/">Home</a>
  <a className="px-2" href="/about">About</a>
  <a className="px-2 me-4" href="/docs">Docs</a>
  <button className="ms-2 px-3">Contact</button>
</nav>
```
