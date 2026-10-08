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
Please refine this draft paragraph until it reads well:

"This module basically provides a helper function that is used for doing some caching stuff behind the scenes. It's pretty much straightforward and should just work out of the box for most use cases, providing a simple and easy way to cache results without much hassle."
