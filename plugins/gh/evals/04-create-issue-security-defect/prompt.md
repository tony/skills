---
max_turns: 15
timeout_seconds: 360
allowed_tools: [Read, Glob, Grep, Skill]
---
File a GitHub issue on example/widgets for this: the `/api/export` handler passes the `file` query parameter straight to `fs.readFile`, so `GET /api/export?file=../../etc/passwd` returns the server's password file to any unauthenticated caller. Reproduced on v2.4.1.
