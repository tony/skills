"""Supplement native eval grades with exact output and retained-artifact checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Generator

if __package__:
    from .fixtures import files_for, source_body
else:
    from fixtures import files_for, source_body  # pyright: ignore[reportImplicitRelativeImport]

CASES = tuple(path.parent.name for path in sorted(Path(__file__).parent.glob("*/case.yaml")))


class EvalError(ValueError):
    """Required evidence failed or is unavailable."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalError(message)


def _mapping(value: object) -> dict[str, object]:
    _require(isinstance(value, dict), "Expected an object in eval evidence")
    return cast("dict[str, object]", value)


def _sequence(value: object) -> list[object]:
    _require(isinstance(value, list), "Expected an array in eval evidence")
    return cast("list[object]", value)


def _string(value: object) -> str:
    _require(isinstance(value, str), "Expected text in eval evidence")
    return cast("str", value)


def _read_json(path: Path) -> dict[str, object]:
    return _mapping(cast("object", json.loads(path.read_text(encoding="utf-8"))))


def goal_payload(reply: str, limit: int | None = None) -> str:
    """Extract exact payload bytes and verify the requested count declaration."""
    matches = list(re.finditer(r"(?m)^## Goal\s*\n+(`{3,})text\n([\s\S]*?)\n\1(?:\n|$)", reply))
    _require(len(matches) == 1, "Expected exactly one complete Goal text block")
    payload = matches[0][2]
    _require(payload.startswith("/goal "), "Printed goal lacks the /goal prefix")
    counts = (len(payload), len(payload.encode("utf-16-le")) // 2)
    outside = reply[: matches[0].start()] + reply[matches[0].end() :]
    declared = re.findall(r"Counts: ([0-9]+) code points; ([0-9]+) UTF-16 units\.", outside)
    _require(declared == [tuple(map(str, counts))], "Printed counts differ from the whole payload")
    if limit is not None:
        _require(max(counts) <= limit, f"Whole payload exceeds {limit} in a counting convention")
    return payload


def _trace(path: Path) -> tuple[Path, str, list[dict[str, object]]]:
    events = [
        _mapping(cast("object", json.loads(line)))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    initial = [event for event in events if event.get("subtype") == "init"]
    results = [event for event in events if event.get("type") == "result"]
    _require(len(initial) == len(results) == 1, "Trace needs one init and terminal result")
    _require(
        any(
            _mapping(plugin).get("name") == "goal-planner"
            for plugin in _sequence(initial[0].get("plugins"))
        ),
        "Plugin was not loaded",
    )
    result = results[0]
    _require(
        result.get("subtype") == "success" and not result.get("is_error"),
        "Eval child did not finish successfully",
    )
    reply = _string(result.get("result"))
    _require(bool(reply), "Trace has no final reply")
    return Path(_string(initial[0].get("cwd"))), reply, events


@contextmanager
def _retained_workspace(original: Path, trace: Path) -> Generator[Path, None, None]:
    if original.is_dir():
        yield original
        return
    sandbox = trace.resolve().parent.parent
    _require(sandbox.name.startswith("claude-eval-"), "Unrecognized retained sandbox")
    _require(original == sandbox / "home/cwd", "Working directory is outside its sandbox")
    sealed = sandbox / "sealed"
    metadata = sealed.lstat()
    _require(stat.S_ISDIR(metadata.st_mode), "Sealed workspace is not a real directory")
    _require(metadata.st_uid == os.getuid(), "Sealed workspace is not owned by this user")
    mode = stat.S_IMODE(metadata.st_mode)
    sealed.chmod(mode | stat.S_IRUSR | stat.S_IXUSR)
    try:
        yield sealed / "home/cwd"
    finally:
        sealed.chmod(mode)


def _inventory(case: str, root: Path, outputs: set[str]) -> None:
    inputs = files_for(case)
    for name, text in inputs.items():
        path = root / name
        _require(path.resolve() == path, f"Fixture input contains a link: {name}")
        _require(path.read_bytes() == text.encode(), f"Fixture input changed: {name}")
    if case in {"02-save-spec", "03-synthesize-revisions"}:
        actual = {str(path.relative_to(root)) for path in root.glob("Documents/*/goal*/*.md")}
        expected = outputs | {name for name in inputs if name.startswith("Documents/")}
        _require(actual == expected, "Unexpected revision, orphan, or missing predecessor")
        _require(not (root / "injected.txt").exists(), "Historical instruction was executed")
        return
    allowed = set(inputs) | outputs | {".claude", ".claude/.cc-writes"}
    for name in tuple(allowed):
        allowed.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
    for path in root.rglob("*"):
        name = str(path.relative_to(root))
        _require(name in allowed, f"Unauthorized output: {name}")
        _require(not path.is_symlink(), f"Fixture contains a link: {name}")
        _require(
            path.is_file() if name in inputs or name in outputs else path.is_dir(),
            f"Unexpected output type: {name}",
        )


def _reused(events: list[dict[str, object]], payload: str, goal: Path) -> bool:
    calls: set[str] = set()
    saved = False
    for event in events:
        if event.get("type") not in {"assistant", "user"}:
            continue
        content = _mapping(event.get("message")).get("content")
        if not isinstance(content, list):
            continue
        for item in cast("list[object]", content):
            block = _mapping(item)
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                calls.add(_string(block.get("id")))
            identifier = block.get("tool_use_id")
            if (
                block.get("type") != "tool_result"
                or identifier not in calls
                or block.get("is_error")
            ):
                continue
            output = block.get("content")
            if not isinstance(output, str):
                output = "\n".join(
                    _string(_mapping(part).get("text")) for part in _sequence(output)
                )
            for match in re.finditer(r"(?m)^\s*\{", output):
                try:
                    decoded = cast(
                        "tuple[object, int]",
                        json.JSONDecoder().raw_decode(output[match.end() - 1 :]),
                    )
                except ValueError:
                    continue
                result = _mapping(decoded[0])
                if result.get("payload") != payload or result.get("goal_path") != str(goal):
                    continue
                if result.get("ready") is not True:
                    continue
                if result.get("reused") is True and saved:
                    return True
                if result.get("reused") is False:
                    saved = True
    return False


def check_case(
    case: str,
    root: Path,
    reply: str,
    events: list[dict[str, object]],
    original: Path | None = None,
) -> None:
    """Check artifacts without importing the planner or executing retained files."""
    _require(case in CASES, f"Unknown case: {case}")
    _require(root.is_absolute() and root.is_dir(), "Retained fixture unavailable; use --keep-temp")
    _require(root.resolve() == root, "Retained fixture contains a linked parent")
    original = root if original is None else original
    outputs: set[str] = set()
    if case == "05-profile-consent":
        outputs = {"preferences.json", "bindings.json"}
        _require(
            _read_json(root / "preferences.json")
            == {
                "schema_version": 1,
                "kind": "profile",
                "approved": True,
                "name": "portable",
                "defaults": {"host": "claude", "save": True, "max_chars": 3800},
                "principles": ["Preserve failed diagnostic evidence."],
            },
            "Profile differs from approved values",
        )
        _require(
            _read_json(root / "bindings.json")
            == {
                "schema_version": 1,
                "kind": "bindings",
                "approved": True,
                "documents_root": str(original / "Documents"),
            },
            "Machine binding differs or is not separate",
        )
    elif case == "04-audit-gates":
        digest = hashlib.sha256((root / "goal.md").read_bytes()).hexdigest()
        _require(digest in reply, "Audit omits the exact reviewed goal digest")
    else:
        limit = None if case == "06-codex-long" else 240 if case == "01-claude-stdout" else 3800
        payload = goal_payload(reply, limit)
        if case == "01-claude-stdout":
            _require("Launch label: 🛰️" in payload, "Unicode label is outside the goal or missing")
        elif case == "06-codex-long":
            _require(payload == "/goal " + source_body(), "Codex goal is not the full exact source")
        else:
            revision = "001" if case == "02-save-spec" else "008"
            name = f"packet-reader-{revision}.md"
            goal = Path("Documents/2030-01-02/goals") / name
            spec = Path("Documents/2030-01-02/goal-specs") / name
            outputs = {str(goal), str(spec)}
            _require(
                all((root / path).resolve() == root / path for path in (goal, spec)),
                "Saved pair contains a link",
            )
            _require(
                (root / goal).read_bytes() == payload.encode(), "Printed and saved bytes differ"
            )
            contract = (root / spec).read_bytes()
            _require(source_body().encode() in contract, "Companion lost complete source content")
            _require(
                str(original / spec) in payload, "Companion locator depends on working directory"
            )
            _require(
                hashlib.sha256(contract).hexdigest() in payload, "Companion digest missing or stale"
            )
            if case == "03-synthesize-revisions":
                _require(
                    _reused(events, payload, original / goal), "No linked tool evidence of reuse"
                )
    _inventory(case, root, outputs)


def check_report(path: Path, selected: str | None = None) -> list[str]:
    """Require complete native grades before inspecting each retained run."""
    report = _read_json(path)
    _require(not report.get("partial"), "Eval report is partial")
    cases = [_mapping(item) for item in _sequence(report.get("cases"))]
    if selected is not None:
        cases = [case for case in cases if case.get("name") == selected]
    expected = {selected} if selected else set(CASES)
    names = [_string(case.get("name")) for case in cases]
    _require(set(names) == expected and len(names) == len(expected), "Missing or duplicate cases")
    for case in cases:
        authored = Path(__file__).parent / _string(case.get("name")) / "case.yaml"
        required = set(
            re.findall(r"^  - name: ([\w-]+)$", authored.read_text(encoding="utf-8"), re.MULTILINE)
        )
        declared = {_string(_mapping(item).get("name")) for item in _sequence(case.get("graders"))}
        _require(
            bool(required) and declared == required, "Authored native graders missing or changed"
        )
        runs = _sequence(_mapping(case.get("arms")).get("with"))
        _require(bool(runs), "No with-plugin runs")
        for item in runs:
            run = _mapping(item)
            _require(not run.get("error") and not run.get("skippedPaidGraders"), "Run incomplete")
            grades = [_mapping(grade) for grade in _sequence(run.get("graders"))]
            _require(
                {_string(grade.get("name")) for grade in grades} == declared
                and len(grades) == len(declared),
                "Missing or duplicate native grades",
            )
            _require(all(grade.get("passed") is True for grade in grades), "Native grader failed")
            trace = Path(_string(run.get("tracePath")))
            trace = trace if trace.is_absolute() else path.parent / trace
            original, reply, events = _trace(trace)
            with _retained_workspace(original, trace) as root:
                check_case(_string(case.get("name")), root, reply, events, original)
    return names


def main() -> int:
    """Check a native report, failing closed when retained evidence is unavailable."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("report", type=Path)
    _ = parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    try:
        checked = check_report(cast("Path", args.report), cast("str | None", args.case))
    except (EvalError, OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: native grades and artifact checks for {len(checked)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
