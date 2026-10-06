---
max_turns: 12
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Trim this SKILL.md with the deletion test. Do not run anything.

```
---
name: cleaning-branches
description: "Use when deleting merged git branches."
allowed-tools: ["Bash"]
---

# Cleaning branches

Branches are a useful part of git workflows, and keeping them tidy matters.

## Delete the branch

Run the command below to delete the branch named `old`:

    ```console
    $ git branch --delete-force old
    ```
```
