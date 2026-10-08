#!/usr/bin/env bash
# Same repo as case 05: a committed repo with a green two-test suite and an off-by-one in bizdays.py.
set -euo pipefail

git init -b main >/dev/null

cat >bizdays.py <<'PY'
def is_business_day(weekday: int) -> bool:
    """Return True for Monday (0) through Friday (4)."""
    return weekday >= 0 and weekday <= 5
PY

cat >test_bizdays.py <<'PY'
import unittest

from bizdays import is_business_day


class BusinessDayTests(unittest.TestCase):
    def test_monday_is_business_day(self):
        self.assertTrue(is_business_day(0))

    def test_sunday_is_not_business_day(self):
        self.assertFalse(is_business_day(6))


if __name__ == "__main__":
    unittest.main()
PY

cat >AGENTS.md <<'MD'
# bizdays

Run the tests with `python3 -m unittest`. No linter or formatter.
MD

printf '.*\n!.gitignore\n' >.gitignore

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add bizdays"
