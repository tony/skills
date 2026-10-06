---
max_turns: 15
timeout_seconds: 420
allowed_tools: [Read, Glob, Grep, Skill]
---
use the strict xfail workflow to fix this bug. The repo has CI, so tell me the full plan, including what you will push and when.

Bug report: `is_business_day(5)` returns `True` for Saturday, but Saturday should not count as a business day.

```python
def is_business_day(weekday: int) -> bool:
    """Return True for Monday (0) through Friday (4)."""
    return weekday >= 0 and weekday <= 5
```
