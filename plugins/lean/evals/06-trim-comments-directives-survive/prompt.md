---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Edit, AskUserQuestion, Skill]
---
Trim the fat comments in this, it is too chatty:

```python
# -*- coding: utf-8 -*-
import os


def load(path):
    """Load the file."""
    # open the file and read it
    data = open(path).read()  # noqa: SIM115
    return data


class NotFound(Exception):
    """Raised when the requested record does not exist in the store, which happens often."""


def parse(raw):
    # This function parses the raw value into an int by calling int on it
    return int(raw)  # type: ignore[arg-type]
```
