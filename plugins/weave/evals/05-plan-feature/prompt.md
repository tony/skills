---
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Bash, Read, Glob, Grep, Write, Skill, Task]
append_system_prompt: >-
  Before input staging, run mkdir -p .eval-state/tmp from the project root.
  For input staging, use mktemp -d "$PWD/.eval-state/tmp/weave-in.XXXXXX"
  from that root, so the input file is inside the writable fixture.
  For this fixture, prefix every weave engine command from the project root
  with AI_AIP_ROOT="$PWD/.eval-state/weave". Set this before init; never
  change roots to bypass a denied write.
---
/weave:plan Add rate limiting to the public API so a single client can't exceed 100 requests per minute. Plan only the limiter module and its API integration seam, in at most four commits; do not scaffold a whole service. Explain normal, exception and capacity paths, and what any memory estimate includes.
