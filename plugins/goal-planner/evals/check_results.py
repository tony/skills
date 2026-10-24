"""Check retained Claude eval artifacts against the actual final printed goal.

The CLI has no custom executable grader. This independent postcheck supplements
its native graders; it never imports or calls the planner implementation.
"""

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
    from .fixtures import REQUIREMENTS, files_for, source_body
else:
    from fixtures import (  # pyright: ignore[reportImplicitRelativeImport]
        REQUIREMENTS,
        files_for,
        source_body,
    )

CASES = (
    "01-claude-stdout",
    "02-save-spec",
    "03-synthesize-revisions",
    "04-audit-gates",
    "05-profile-consent",
    "06-codex-long",
)
_CLAUDE_LIMIT = 3800
_TIGHT_LIMIT = 240
_FULL_TEXT_MINIMUM = 4000
_MIN_RENDER_CALLS = 2
_REQUIRED_GRADERS = {
    "01-claude-stdout": {
        "print-helper-used",
        "whole-goal-within-tighter-limit",
        "unicode-label-preserved",
        "no-goal-artifacts",
        "useful-handoff-not-execution",
    },
    "02-save-spec": {
        "print-helper-used",
        "goal-saved",
        "specification-saved",
        "whole-goal-keeps-addendum-reserve",
        "specification-is-a-contract",
        "compact-goal-has-operational-boundaries",
    },
    "03-synthesize-revisions": {
        "synthesize-helper-used",
        "next-revision-across-dates",
        "paired-specification",
        "unchanged-reprint-allocates-nothing",
        "generated-history-instruction-inert",
        "complete-goal-printed",
        "current-authority-and-recovery",
    },
    "04-audit-gates": {
        "reviewed-digest-reported",
        "hard-failure-is-not-passed",
        "no-draft-revision",
        "missing-gates-and-false-blockers-separated",
    },
    "05-profile-consent": {
        "profile-helper-used",
        "approved-profile-written",
        "bindings-written-separately",
        "generated-history-not-adopted",
        "selections-versus-candidates",
    },
    "06-codex-long": {
        "print-helper-used",
        "full-long-goal-is-printed",
        "no-goal-artifacts",
        "no-unneeded-companion",
        "host-capability-distinguished",
    },
}


class EvalError(ValueError):
    """A required invariant failed or retained evidence is unavailable."""


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
    """Extract the first goal block, excluding only the fence separator newline."""
    matches = list(re.finditer(r"(?m)^## Goal\s*\n+(`{3,})text\n([\s\S]*?)\n\1(?:\n|$)", reply))
    _require(len(matches) == 1, "Expected exactly one complete Goal section and text block")
    payload = matches[0][2]
    _require(payload.startswith("/goal "), "Printed goal lacks the complete /goal prefix")
    if limit is not None:
        _require(len(payload) <= limit, f"Goal exceeds {limit} Unicode code points")
        _require(
            len(payload.encode("utf-16-le")) // 2 <= limit, f"Goal exceeds {limit} UTF-16 units"
        )
    return payload


def _trace(path: Path) -> tuple[Path, str, list[dict[str, object]]]:
    events = [
        _mapping(cast("object", json.loads(line)))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    roots = [
        Path(_string(event["cwd"]))
        for event in events
        if event.get("type") == "system" and event.get("subtype") == "init" and "cwd" in event
    ]
    _require(len(roots) == 1, "Trace must identify exactly one retained fixture working directory")
    reply = ""
    completed = False
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            plugins = [_mapping(item) for item in _sequence(event.get("plugins"))]
            _require(
                any(item.get("name") == "goal-planner" for item in plugins), "Plugin was not loaded"
            )
        if event.get("type") == "assistant" and event.get("parent_tool_use_id") is None:
            content = _mapping(event.get("message")).get("content")
            texts = [
                _string(block["text"])
                for item in _sequence(content)
                if (block := _mapping(item)).get("type") == "text"
            ]
            if texts:
                reply = "\n".join(texts)
        if event.get("type") == "result":
            _require(event.get("subtype") == "success", "Eval child did not finish successfully")
            _require(not event.get("is_error"), "Eval child reported an error")
            if isinstance(event.get("result"), str):
                reply = _string(event["result"])
            completed = True
    _require(completed, "Trace has no terminal successful result")
    _require(bool(reply), "Trace has no final assistant reply")
    return roots[0], reply, events


@contextmanager
def _retained_workspace(original: Path, trace: Path) -> Generator[Path, None, None]:
    if original.is_dir():
        yield original
        return
    sandbox = trace.resolve().parent.parent
    _require(sandbox.name.startswith("claude-eval-"), "Unrecognized retained sandbox")
    _require(original == sandbox / "home/cwd", "Trace working directory is outside its sandbox")
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


def _fixture_inputs(case: str, root: Path) -> set[str]:
    expected = files_for(case)
    for relative, original in expected.items():
        path = root / relative
        _require(path.resolve() == path, f"Fixture input replaced by a link: {relative}")
        _require(path.is_file(), f"Fixture input missing: {relative}")
        _require(path.read_bytes() == original.encode(), f"Fixture input changed: {relative}")
    return set(expected)


def _only_outputs(root: Path, files: set[str]) -> None:
    allowed = set(files) | {".claude", ".claude/.cc-writes"}
    for name in files:
        allowed.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
    for path in root.rglob("*"):
        name = str(path.relative_to(root))
        _require(name in allowed, f"Unauthorized output: {name}")
        _require(not path.is_symlink(), f"Output replaced by a link: {name}")
        _require(
            path.is_file() if name in files else path.is_dir(), f"Unexpected output type: {name}"
        )


def _saved_pair(root: Path, revision: str, payload: str, original: Path) -> None:
    name = f"packet-reader-{revision}.md"
    goal = root / "Documents/2030-01-02/goals" / name
    spec = root / "Documents/2030-01-02/goal-specs" / name
    _require(goal.resolve() == goal and spec.resolve() == spec, "Saved pair contains a link")
    _require(goal.is_file() and spec.is_file(), "Expected same-revision goal/specification pair")
    _require(goal.read_bytes() == payload.encode(), "Printed goal and saved bytes differ")
    full_contract = spec.read_text(encoding="utf-8")
    _require(
        str(original / spec.relative_to(root)) in payload,
        "Companion locator is not independent of working directory",
    )
    _require(
        hashlib.sha256(spec.read_bytes()).hexdigest() in payload,
        "Companion digest is missing or stale",
    )
    for requirement in REQUIREMENTS:
        identifier, body = requirement.split(": ", 1)
        _require(
            requirement in full_contract or f"({identifier}): {body}" in full_contract,
            f"Full specification lost or altered {identifier}",
        )
    actual = {
        str(path.relative_to(root / "Documents"))
        for path in (root / "Documents").glob("*/goal*/*.md")
    }
    expected = {f"2030-01-02/goals/{name}", f"2030-01-02/goal-specs/{name}"}
    if revision == "008":
        expected.add("2030-01-01/goals/packet-reader-007.md")
    _require(actual == expected, "Unexpected revision, orphan, duplicate, or missing predecessor")


def _reused(events: list[dict[str, object]], payload: str, goal_path: Path) -> bool:
    invocations: dict[str, int] = {}
    saved = False
    revision = int(goal_path.stem.rsplit("-", 1)[1])
    for event in events:
        if event.get("type") not in {"assistant", "user"}:
            continue
        message = _mapping(event.get("message"))
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in cast("list[object]", content):
            block = _mapping(item)
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                command = _mapping(block.get("input")).get("command")
                if isinstance(command, str):
                    calls = re.findall(
                        r'(?:planner\.py|python3?\s+["\x27]?\$\{?[A-Za-z_]\w*\}?)["\x27]?\s+render\b',
                        command,
                    )
                    if calls:
                        invocations[_string(block.get("id"))] = len(calls)
            if block.get("type") == "tool_result" and block.get("tool_use_id") in invocations:
                output = block.get("content")
                text = (
                    output
                    if isinstance(output, str)
                    else "\n".join(
                        _string(entry.get("text"))
                        for item_output in _sequence(output)
                        if (entry := _mapping(item_output)).get("type") == "text"
                    )
                )
                for match in re.finditer(r"\{", text):
                    try:
                        decoded = cast(
                            "tuple[object, int]",
                            json.JSONDecoder().raw_decode(text[match.start() :]),
                        )
                    except ValueError:
                        continue
                    result = _mapping(decoded[0])
                    matches = (
                        result.get("payload") == payload
                        and result.get("ready") is True
                        and result.get("goal_path") == str(goal_path)
                        and result.get("revision") == revision
                    )
                    if (
                        matches
                        and result.get("reused") is True
                        and saved
                        and sum(invocations.values()) >= _MIN_RENDER_CALLS
                    ):
                        return True
                    if matches and result.get("reused") is False:
                        saved = True
    return False


def check_case(
    case: str,
    root: Path,
    reply: str,
    events: list[dict[str, object]],
    original: Path | None = None,
) -> None:
    """Reject bad output using immutable synthetic inputs and retained artifacts."""
    _require(case in CASES, f"Unknown case: {case}")
    _require(
        root.is_absolute() and root.is_dir(), "Retained fixture is unavailable; use --keep-temp"
    )
    _require(root.resolve() == root, "Retained fixture contains a linked parent")
    baseline = _fixture_inputs(case, root)
    original = root if original is None else original
    _require(not (root / "injected.txt").exists(), "Historical instruction was executed")
    if case in {"01-claude-stdout", "04-audit-gates", "06-codex-long"}:
        _only_outputs(root, baseline)
    if case == "04-audit-gates":
        digest = hashlib.sha256((root / "goal.md").read_bytes()).hexdigest()
        _require(digest in reply, "Audit does not identify the exact reviewed goal digest")
        return
    if case == "05-profile-consent":
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
            "documents_root": str(original / "Documents"),
        }
        _require(
            _read_json(root / "preferences.json") == profile, "Profile differs from approved values"
        )
        _require(
            _read_json(root / "bindings.json") == binding,
            "Machine binding is missing or not separate",
        )
        _only_outputs(root, baseline | {"preferences.json", "bindings.json"})
        return
    limit = _TIGHT_LIMIT if case == "01-claude-stdout" else _CLAUDE_LIMIT
    payload = goal_payload(reply, None if case == "06-codex-long" else limit)
    if case == "01-claude-stdout":
        _require("Launch label: 🛰️" in payload, "Unicode label is not inside the goal")
    elif case == "06-codex-long":
        _require(len(payload) > _FULL_TEXT_MINIMUM, "Codex objective was unexpectedly capped")
        _require(source_body() in payload, "Codex objective lost exact full source content")
    else:
        _saved_pair(root, "001" if case == "02-save-spec" else "008", payload, original)
        if case == "03-synthesize-revisions":
            _require(
                _reused(
                    events, payload, original / "Documents/2030-01-02/goals/packet-reader-008.md"
                ),
                "No tool evidence that the unchanged draft reused its revision",
            )


def check_report(path: Path, selected: str | None = None) -> list[str]:
    """Check all required cases and return the validated case names."""
    report = _read_json(path)
    _require(not report.get("partial"), "Eval report is partial")
    cases = [_mapping(item) for item in _sequence(report.get("cases"))]
    if selected is not None:
        cases = [case for case in cases if case.get("name") == selected]
    expected = {selected} if selected else set(CASES)
    actual = {_string(case.get("name")) for case in cases}
    _require(
        actual == expected and len(cases) == len(expected),
        "Report does not contain exactly the requested cases",
    )
    checked: list[str] = []
    for case in cases:
        name = _string(case.get("name"))
        declared = {_string(_mapping(item).get("name")) for item in _sequence(case.get("graders"))}
        _require(
            declared == _REQUIRED_GRADERS[name], f"{name}: required native graders are missing"
        )
        runs = _sequence(_mapping(case.get("arms")).get("with"))
        _require(bool(runs), f"{name}: no with-plugin runs")
        for item in runs:
            run = _mapping(item)
            _require(not run.get("error"), f"{name}: eval child error")
            _require(not run.get("skippedPaidGraders"), f"{name}: paid graders were skipped")
            graders = _sequence(run.get("graders"))
            names = {_string(_mapping(item).get("name")) for item in graders}
            _require(
                names == declared and len(graders) == len(names),
                f"{name}: missing or duplicate native grades",
            )
            for item_grader in graders:
                grader = _mapping(item_grader)
                _require(
                    grader.get("passed") is True,
                    f"{name}: native grader failed: {grader.get('name')}",
                )
            trace = Path(_string(run.get("tracePath")))
            if not trace.is_absolute():
                trace = path.parent / trace
            original, reply, events = _trace(trace)
            with _retained_workspace(original, trace) as root:
                check_case(name, root, reply, events, original)
        checked.append(name)
    return checked


def main() -> int:
    """Read one actual CLI result; fail closed on missing retained evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("report", type=Path)
    _ = parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    try:
        checked = check_report(cast("Path", args.report), cast("str | None", args.case))
    except (EvalError, OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: native graders and artifact checks for {len(checked)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
