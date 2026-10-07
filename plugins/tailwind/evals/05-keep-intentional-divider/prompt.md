---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Audit the spacing in this Tailwind header. Apply the fixes directly, no questions, I'm heads-down:

```tsx
<header className="flex items-center gap-2 px-4">
  <a href="/" className="px-2">Home</a>
  <a href="/docs" className="px-2">Docs</a>
  <div className="mx-6 h-5 w-px bg-slate-300" aria-hidden="true" />
  <a href="/login" className="px-2">Log in</a>
  <a href="/signup" className="px-2">Sign up</a>
</header>
```
