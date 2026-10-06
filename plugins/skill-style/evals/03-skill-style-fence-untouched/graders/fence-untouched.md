---
type: llm
---
Wherever the reply reproduces the fenced command, it keeps `git branch --delete-force old` character for character, and it does not substitute `-D`, `--delete --force`, or any other spelling.
The reply reports `--delete-force` as a flaw (not a real git flag) for the author to fix, rather than correcting it inside the skill text.
The reply cuts or flags the filler sentence about branches being useful.
