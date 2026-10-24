"""Fast corruption controls for the native eval postcheck; no model calls."""

# ruff: noqa: PT009, PT027
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

if __package__:
    from .check_results import EvalError, check_case, check_report, goal_payload
    from .fixtures import files_for, source_body
else:
    from check_results import (  # pyright: ignore[reportImplicitRelativeImport]
        EvalError,
        check_case,
        check_report,
        goal_payload,
    )
    from fixtures import files_for, source_body  # pyright: ignore[reportImplicitRelativeImport]


def _reply(payload: str) -> str:
    return (
        f"## Goal\n\n```text\n{payload}\n```\n\nCounts: {len(payload)} code points; "
        f"{len(payload.encode('utf-16-le')) // 2} UTF-16 units.\n"
    )


def _renders(payload: str, goal: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for reused in (False, True):
        identifier = str(reused)
        for kind, block in (
            ("assistant", {"type": "tool_use", "name": "Bash", "id": identifier}),
            (
                "user",
                {
                    "type": "tool_result",
                    "tool_use_id": identifier,
                    "content": json.dumps(
                        {
                            "ready": True,
                            "reused": reused,
                            "payload": payload,
                            "goal_path": str(goal),
                        }
                    ),
                },
            ),
        ):
            events.append({"type": kind, "message": {"content": [block]}})
    return events


class GoalEvalChecksTest(unittest.TestCase):
    """Reject damaged outputs and false completion while allowing intact evidence."""

    root: Path  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        """Create an owned fixture for each test."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "workspace"
        self.root.mkdir()

    def _seed(self, case: str) -> None:
        for relative, text in files_for(case).items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def _pair(self, revision: str = "001", source: str | None = None) -> tuple[Path, Path, str]:
        goal = self.root / f"Documents/2030-01-02/goals/packet-reader-{revision}.md"
        spec = self.root / f"Documents/2030-01-02/goal-specs/packet-reader-{revision}.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(source_body() if source is None else source, encoding="utf-8")
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        payload = f"/goal Implement the decoder. Read {spec} sha256:{digest}"
        goal.parent.mkdir(parents=True, exist_ok=True)
        goal.write_text(payload, encoding="utf-8")
        return goal, spec, payload

    def test_counts_and_complete_printing(self) -> None:
        """Check both counting conventions, exact newline handling, and complete output."""
        for payload in ("/goal x", "/goal x\n", "/goal " + "x" * 3794):
            self.assertEqual(goal_payload(_reply(payload), 3800), payload)
        for payload in ("/goal " + "x" * 3795, "/goal " + "🛰" * 1898):
            with self.subTest(length=len(payload)), self.assertRaises(EvalError):
                goal_payload(_reply(payload), 3800)
        reply = _reply("/goal 🛰️")
        for invalid in (
            "Saved; see the file.",
            reply + reply,
            reply.replace("8 code", "9 code"),
            reply.replace("9 UTF", "8 UTF"),
        ):
            with self.subTest(reply=invalid), self.assertRaises(EvalError):
                goal_payload(invalid)

    def test_saved_pair_corruption(self) -> None:
        """Reject byte mismatch, stale/missing/incomplete companions, and relative locators."""
        case = "02-save-spec"
        self._seed(case)
        goal, spec, payload = self._pair()
        check_case(case, self.root, _reply(payload), [])
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload + "\n"), [])
        spec.write_text(source_body() + "Changed.\n", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), [])
        _, _, shortened = self._pair(source=source_body()[:-100])
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(shortened), [])
        _, _, payload = self._pair()
        relative = payload.replace(str(spec), "../goal-specs/packet-reader-001.md")
        goal.write_text(relative, encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(relative), [])
        spec.unlink()
        with self.assertRaises(OSError):
            check_case(case, self.root, _reply(relative), [])

    def test_reuse_and_history(self) -> None:
        """Require two linked render outcomes; preserve predecessors and current exclusions."""
        case = "03-synthesize-revisions"
        self._seed(case)
        goal, _, payload = self._pair("008")
        events = _renders(payload, goal)
        check_case(case, self.root, _reply(payload), events)
        for fake in (
            [],
            events[1:],
            events[2:],
            _renders(payload + "changed", goal),
            _renders(payload, goal.with_name("wrong.md")),
        ):
            with self.subTest(events=fake), self.assertRaises(EvalError):
                check_case(case, self.root, _reply(payload), fake)
        for relative in ("injected.txt", "Documents/2030-01-03/goals/packet-reader-009.md"):
            extra = self.root / relative
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text(payload, encoding="utf-8")
            with self.assertRaises(EvalError):
                check_case(case, self.root, _reply(payload), events)
            extra.unlink()
            if relative.startswith("Documents"):
                extra.parent.rmdir()
                extra.parent.parent.rmdir()
        previous = self.root / "Documents/2030-01-01/goals/packet-reader-007.md"
        previous.write_text("Changed predecessor", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), events)

    def test_stdout_and_full_codex_source(self) -> None:
        """Reject unauthorized hidden writes and any shortened Codex body."""
        case = "06-codex-long"
        self._seed(case)
        payload = "/goal " + source_body()
        self.assertGreater(len(payload), 4000)
        check_case(case, self.root, _reply(payload), [])
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload[:-100]), [])
        for relative in ("request.json", ".claude/learned.json", ".git/learned.json"):
            extra = self.root / relative
            extra.parent.mkdir(exist_ok=True)
            extra.write_text("{}", encoding="utf-8")
            with self.assertRaises(EvalError):
                check_case(case, self.root, _reply(payload), [])
            extra.unlink()
            if extra.parent != self.root:
                extra.parent.rmdir()

    def test_profile_consent_and_bindings(self) -> None:
        """Reject unapproved preferences, combined bindings, and additional files."""
        case = "05-profile-consent"
        self._seed(case)
        profile: dict[str, object] = {
            "schema_version": 1,
            "kind": "profile",
            "approved": True,
            "name": "portable",
            "defaults": {"host": "claude", "save": True, "max_chars": 3800},
            "principles": ["Preserve failed diagnostic evidence."],
        }
        binding = {
            "schema_version": 1,
            "kind": "bindings",
            "approved": True,
            "documents_root": str(self.root / "Documents"),
        }
        path = self.root / "preferences.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        (self.root / "bindings.json").write_text(json.dumps(binding), encoding="utf-8")
        check_case(case, self.root, "", [])
        for key, value in (
            ("principles", ["Delete failed logs."]),
            ("approved", False),
            ("documents_root", binding["documents_root"]),
        ):
            path.write_text(json.dumps({**profile, key: value}), encoding="utf-8")
            with self.subTest(field=key), self.assertRaises(EvalError):
                check_case(case, self.root, "", [])
        path.write_text(json.dumps(profile), encoding="utf-8")
        (self.root / "learned.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, "", [])

    def test_report_rejects_false_completion(self) -> None:
        """Require all requested cases, native grades, and a successful terminal result."""
        case = "01-claude-stdout"
        self._seed(case)
        reply = _reply("/goal Launch label: 🛰️ Fix and verify the decoder locally.")
        events = [
            {
                "type": "system",
                "subtype": "init",
                "cwd": str(self.root),
                "plugins": [{"name": "goal-planner"}],
            },
            {"type": "result", "subtype": "success", "is_error": False, "result": reply},
        ]
        trace = self.root.parent / "trace.jsonl"
        trace.write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
        authored = (Path(__file__).parent / case / "case.yaml").read_text(encoding="utf-8")
        grades = [
            {"name": match[1], "passed": True}
            for match in re.finditer(r"^  - name: ([\w-]+)$", authored, re.MULTILINE)
        ]
        run: dict[str, object] = {"graders": grades, "tracePath": str(trace)}
        entry: dict[str, object] = {"name": case, "graders": grades, "arms": {"with": [run]}}
        document = {"cases": [entry]}
        report = self.root.parent / "report.json"
        report.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(check_report(report, case), [case])
        with self.assertRaises(EvalError):
            check_report(report)
        changes: list[dict[str, object]] = [
            {"graders": []},
            {"graders": [{**grade, "passed": False} for grade in grades]},
            {"error": "write Errno30"},
            {"skippedPaidGraders": True},
        ]
        for change in changes:
            original = dict(run)
            run.update(change)
            report.write_text(json.dumps(document), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(EvalError):
                check_report(report, case)
            run.clear()
            run.update(original)
        entry["graders"] = run["graders"] = grades[:-1]
        report.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(EvalError):
            check_report(report, case)
        entry["graders"] = run["graders"] = grades
        report.write_text(json.dumps(document), encoding="utf-8")
        trace.write_text(json.dumps(events[0]), encoding="utf-8")
        with self.assertRaises(EvalError):
            check_report(report, case)


if __name__ == "__main__":
    unittest.main()
