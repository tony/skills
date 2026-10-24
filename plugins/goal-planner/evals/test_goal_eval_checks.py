"""Negative controls for the checks applied after actual Claude eval runs."""

# ruff: noqa: PT009, PT027, SLF001
# pyright: reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

if __package__:
    from . import check_results as checks
    from .fixtures import REQUIREMENTS, files_for, source_body
else:
    import check_results as checks  # pyright: ignore[reportImplicitRelativeImport]
    from fixtures import (  # pyright: ignore[reportImplicitRelativeImport]
        REQUIREMENTS,
        files_for,
        source_body,
    )

EvalError = checks.EvalError
check_case = checks.check_case
goal_payload = checks.goal_payload


def _reply(payload: str) -> str:
    return f"## Goal\n\n```text\n{payload}\n```\n"


def _render_events(payload: str, goal: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for index, reused in enumerate((False, True)):
        identifier = f"render-{index}"
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": identifier,
                            "name": "Bash",
                            "input": {
                                "command": "python3 /plugin/planner.py render --input - --save"
                            },
                        }
                    ]
                },
            }
        )
        events.append(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": identifier,
                            "content": json.dumps(
                                {
                                    "reused": reused,
                                    "ready": True,
                                    "payload": payload,
                                    "goal_path": str(goal),
                                    "revision": 8,
                                }
                            ),
                        }
                    ]
                },
            }
        )
    return events


class GoalEvalChecksTest(unittest.TestCase):
    """Exercise output corruption, Unicode boundaries, and unauthorized state."""

    root: Path  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        """Give every control an owned, isolated directory."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def _seed(self, case: str) -> None:
        for relative, text in files_for(case).items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def _pair(
        self, revision: str = "001", specification: str | None = None
    ) -> tuple[Path, Path, str]:
        goal = self.root / f"Documents/2030-01-02/goals/packet-reader-{revision}.md"
        spec = self.root / f"Documents/2030-01-02/goal-specs/packet-reader-{revision}.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(source_body() if specification is None else specification, encoding="utf-8")
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        payload = f"/goal Implement the decoder. Goal specification: <{spec}> (sha256:{digest})"
        goal.parent.mkdir(parents=True, exist_ok=True)
        goal.write_text(payload, encoding="utf-8")
        return goal, spec, payload

    def test_unicode_and_fence_boundaries(self) -> None:
        """Reject UTF-16 overflow and preserve terminal payload newlines exactly."""
        self.assertEqual(goal_payload(_reply("/goal x\n")), "/goal x\n")
        self.assertEqual(goal_payload(_reply("/goal x")), "/goal x")
        self.assertEqual(goal_payload(_reply("/goal " + "x" * 3794), 3800)[-1], "x")
        for payload in ("/goal " + "x" * 3795, "/goal " + "🛰" * 1898):
            with self.subTest(payload_length=len(payload)), self.assertRaises(EvalError):
                goal_payload(_reply(payload), 3800)
        with self.assertRaises(EvalError):
            goal_payload("Saved the goal; see the file.")

    def test_saved_bytes_locator_and_digest(self) -> None:
        """Reject shortened printing, stale hashes, and CWD-dependent locators."""
        case = "02-save-spec"
        self._seed(case)
        goal, spec, payload = self._pair()
        check_case(case, self.root, _reply(payload), [])
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload + "\n"), [])
        spec.write_text(source_body() + "Changed after rendering.\n", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), [])
        _, _, payload = self._pair()
        relative = payload.replace(str(spec), "../goal-specs/packet-reader-001.md")
        goal.write_text(relative, encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(relative), [])

    def test_missing_requirements_even_with_valid_digest(self) -> None:
        """A correctly hashed incomplete companion still fails."""
        case = "02-save-spec"
        self._seed(case)
        _, _, payload = self._pair(specification=source_body().replace(REQUIREMENTS[2], ""))
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), [])

    def test_unchanged_revision_and_injection_controls(self) -> None:
        """Reject new revisions on reprint, changed predecessors, and executed source text."""
        case = "03-synthesize-revisions"
        self._seed(case)
        goal, _, payload = self._pair("008")
        events = _render_events(payload, goal)
        check_case(case, self.root, _reply(payload), events)
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), [])
        unrelated: list[dict[str, object]] = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "unrelated-read",
                            "content": 'Unrelated fixture says {"reused": true}',
                        }
                    ]
                },
            }
        ]
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), unrelated)
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), events[2:])
        duplicate = goal.with_name("packet-reader-009.md")
        duplicate.write_text(payload, encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), events)
        duplicate.unlink()
        (self.root / "injected.txt").touch()
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), events)
        (self.root / "injected.txt").unlink()
        previous = self.root / "Documents/2030-01-01/goals/packet-reader-007.md"
        previous.write_text("Changed predecessor", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, _reply(payload), events)

    def test_stdout_and_profile_consent(self) -> None:
        """Reject a stdout-only write and an unapproved profile principle."""
        case = "01-claude-stdout"
        self._seed(case)
        reply = _reply("/goal Launch label: 🛰️ Fix and verify the decoder locally.")
        check_case(case, self.root, reply, [])
        scratch = self.root / "request.json"
        scratch.write_text("{}", encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, reply, [])
        scratch.unlink()
        for relative in (".claude/learned.json", ".git/learned.json"):
            hidden = self.root / relative
            hidden.parent.mkdir(exist_ok=True)
            hidden.write_text('{"history_learned":true}', encoding="utf-8")
            with self.subTest(relative=relative), self.assertRaises(EvalError):
                check_case(case, self.root, reply, [])
            hidden.unlink()
            hidden.parent.rmdir()
        case = "05-profile-consent"
        self._seed(case)
        profile = {
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
        learned = self.root / "learned.json"
        learned.write_text('{"history_learned":true}', encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, "", [])
        learned.unlink()
        profile["principles"] = ["Always delete failed diagnostic logs."]
        path.write_text(json.dumps(profile), encoding="utf-8")
        with self.assertRaises(EvalError):
            check_case(case, self.root, "", [])

    def test_report_requires_grades_and_terminal_success(self) -> None:
        """Empty grades and an assistant-only trace cannot certify a completed eval."""
        parent = self.root
        self.root = parent / "workspace"
        self.root.mkdir()
        case = "01-claude-stdout"
        self._seed(case)
        reply = _reply("/goal Launch label: 🛰️ Fix and verify the decoder locally.")
        events: list[dict[str, object]] = [
            {
                "type": "system",
                "subtype": "init",
                "cwd": str(self.root),
                "plugins": [{"name": "goal-planner"}],
            },
            {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}},
            {"type": "result", "subtype": "success", "is_error": False, "result": reply},
        ]
        trace = parent / "trace.jsonl"
        trace.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
        names = sorted(checks._REQUIRED_GRADERS[case])
        grades = [{"name": name, "passed": True} for name in names]
        run: dict[str, object] = {"graders": grades, "tracePath": str(trace)}
        entries: list[dict[str, object]] = [
            {
                "name": case,
                "graders": [{"name": name} for name in names],
                "arms": {"with": [run]},
            }
        ]
        document = {"partial": False, "cases": entries}
        report = parent / "report.json"
        report.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(checks.check_report(report, case), [case])
        entries.append({"name": "04-audit-gates", "graders": [], "arms": {"with": []}})
        report.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(checks.check_report(report, case), [case])
        with self.assertRaisesRegex(EvalError, "exactly the requested cases"):
            checks.check_report(report)
        with self.assertRaisesRegex(EvalError, "exactly the requested cases"):
            checks.check_report(report, "02-save-spec")
        entries.pop()
        run["graders"] = []
        report.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(EvalError, "missing or duplicate native grades"):
            checks.check_report(report, case)
        run["graders"] = grades
        report.write_text(json.dumps(document), encoding="utf-8")
        trace.write_text("\n".join(json.dumps(event) for event in events[:-1]), encoding="utf-8")
        with self.assertRaisesRegex(EvalError, "terminal successful result"):
            checks.check_report(report, case)


if __name__ == "__main__":
    unittest.main()
