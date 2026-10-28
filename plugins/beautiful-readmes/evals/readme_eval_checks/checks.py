"""Check retained native-eval artifacts independently of the prose judge."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import re
import shlex
import stat
import subprocess
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Generator


def _fail(message: str) -> t.NoReturn:
    raise ValueError(message)


def verify(root: Path, name: str, hashes: dict[str, str]) -> None:
    """Reject changed inputs, missing outputs and broken fixture examples."""
    project = root / "project"
    source = Path(__file__).parents[1] / "fixtures" / name
    for relative, expected in hashes.items():
        actual = hashlib.sha256((project / relative).read_bytes()).hexdigest()
        if actual != expected:
            _fail(f"Input changed: {relative}")
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != expected:
            _fail(f"Verifier fixture differs from the evaluated input: {relative}")
    if name == "audit-only":
        if not (root / "outputs/audit.md").is_file():
            _fail("Missing assessment")
        return
    output = root / (
        "outputs/project/README.md" if name == "generated-font" else "outputs/README.md"
    )
    text = output.read_text(encoding="utf-8")
    base = output.parent if name == "generated-font" else project
    for link in t.cast("list[str]", re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)):
        if re.match(r"https?://", link) or link.startswith("#"):
            continue
        if not (base / link.split("#", 1)[0]).exists():
            _fail(f"Broken local link: {link}")
    if name == "generated-font":
        if output.read_bytes() != (base / "docs/README.template.md").read_bytes():
            _fail("Generated README differs from its owner")
        for relative in ["docs/font-license.md", "docs/script-license.md"]:
            if (base / relative).read_bytes() != (project / relative).read_bytes():
                _fail(f"License changed: {relative}")
    if name in {"preserve-library", "long-manual"}:
        required = (
            ["usage", "limitations"]
            if name == "preserve-library"
            else ["inspect", "validate", "convert", "recover", "formats", "exit-codes"]
        )
        headings = t.cast("list[str]", re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE))
        anchors = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings}
        anchors.update(re.findall(r"""id=["']([^"']+)["']""", text))
        if not set(required) <= anchors:
            _fail("Existing incoming anchors were lost")
    if name in {"new-cli", "client-routes"}:
        _commands(source, text, name)
    if name == "preserve-library":
        expected = ast.dump(
            ast.parse('from glyphwrap import wrap\nprint(wrap("one two three", width=7))')
        )
        examples = t.cast("list[str]", re.findall(r"```python\n(.*?)```", text, re.DOTALL))
        if not any(ast.dump(ast.parse(code)) == expected for code in examples):
            _fail("The working example changed behavior")
    if name == "example-contracts":
        _example(source, text)


def _commands(project: Path, text: str, name: str) -> None:
    wanted = "tallylines.py" if name == "new-cli" else "bridge.py"
    clients: set[str] = set()
    blocks = t.cast(
        "list[str]", re.findall(r"```(?:console|sh|shell|bash|zsh)\n(.*?)```", text, re.DOTALL)
    )
    for line in "\n".join(blocks).splitlines():
        command = line.strip().removeprefix("$ ")
        if not re.match(r"python(?:3)?\s", command):
            continue
        args = shlex.split(command)
        if args[1:2] != [wanted]:
            continue
        if name == "new-cli" and args[2:] != ["sample.txt"]:
            _fail("Example does not run the supplied sample")
        if name == "client-routes" and args[2:] not in [
            ["--client", "claude-code"],
            ["--client", "codex"],
        ]:
            _fail("Example does not select a supported client")
        completed = subprocess.run(  # noqa: S603 -- script and arguments are allowlisted above.
            [sys.executable, "-I", str(project / args[1]), *args[2:]],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        if name == "new-cli" and completed.stdout.strip() != "2":
            _fail("Documented command did not produce 2")
        clients.add(args[-1])
    if name == "new-cli" and not clients:
        _fail("No runnable first-use command")
    if name == "client-routes" and clients != {"claude-code", "codex"}:
        _fail("A supported client route was lost")


def _example(project: Path, text: str) -> None:
    examples = t.cast("list[str]", re.findall(r"```python\n(.*?)```", text, re.DOTALL))
    if not examples:
        _fail("Missing standalone Python example")
    code = examples[0]
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or (
            isinstance(node, ast.ImportFrom) and node.module != "toybridge"
        ):
            _fail("Example imports outside the supplied fixture")
        if isinstance(node, ast.Attribute) and node.attr not in {
            "select_layout",
            "close",
            "events",
            "name",
        }:
            _fail("Example accesses an unrelated API")
        if isinstance(node, ast.Call):
            call = node.func
            if isinstance(call, ast.Name) and call.id in {"temporary_server", "Server", "print"}:
                continue
            if isinstance(call, ast.Attribute) and call.attr in {"select_layout", "close"}:
                continue
            _fail("Example calls outside the supplied API")
    bootstrap = "import sys; sys.path.insert(0, " + repr(str(project)) + ")\n" + code
    _ = subprocess.run(  # noqa: S603 -- imports and calls are limited to the inert fixture API.
        [sys.executable, "-I", "-S", "-c", bootstrap],
        cwd=project,
        check=True,
        timeout=2,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(project), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError
    return t.cast("dict[str, object]", value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError
    return t.cast("list[object]", value)


def _bind_record(
    case: str, run: dict[str, object], records: list[dict[str, object]]
) -> dict[str, object]:
    trace = run.get("tracePath")
    if not isinstance(trace, str):
        _fail("Native run has no trace path")
    trial = Path(trace).parent.parent
    matches = [
        record
        for record in records
        if record.get("case") == case
        and isinstance(record.get("root"), str)
        and Path(t.cast("str", record["root"])).is_relative_to(trial)
    ]
    if len(matches) != 1:
        _fail("Missing unique scaffold evidence for this case and arm")
    return matches[0]


@contextlib.contextmanager
def _workspace(recorded: Path, trace: Path) -> Generator[Path, None, None]:
    """Read the native runner's relocated data without executing inside it."""
    if recorded.is_dir():
        yield recorded
        return
    trial = trace.parent.parent
    if not recorded.is_relative_to(trial):
        _fail("Workspace is outside its native trial")
    sealed = trial / "sealed"
    if sealed.is_symlink() or not sealed.is_dir():
        _fail("Retained native workspace is unavailable")
    mode = stat.S_IMODE(sealed.stat().st_mode)
    try:
        sealed.chmod(mode | stat.S_IRUSR | stat.S_IXUSR)
        relocated = sealed / recorded.relative_to(trial)
        if not relocated.is_dir():
            _fail("Retained native workspace is unavailable")
        yield relocated
    finally:
        sealed.chmod(mode)


def _native_cases(report: dict[str, object]) -> tuple[dict[str, dict[str, object]], list[str]]:
    cases: dict[str, dict[str, object]] = {}
    issues: list[str] = []
    for item in _array(report.get("cases")):
        case = _object(item)
        name = case.get("name")
        if not isinstance(name, str) or name in cases:
            issues.append("Invalid or duplicate native case")
            continue
        cases[name] = case
    return cases, issues


def check_report(report: dict[str, object], directory: Path) -> dict[str, object]:
    """Require complete arm accounting; baseline quality remains a comparison."""
    expected = {p.parent.name for p in Path(__file__).parents[1].glob("*/case.yaml")}
    cases, issues = _native_cases(report)
    if set(cases) != expected:
        issues.append("Native report does not contain every expected case exactly once")
    records = [
        _object(t.cast("object", json.loads(p.read_text(encoding="utf-8"))))
        for p in directory.glob("*.json")
    ]
    rows: list[dict[str, object]] = []
    for name in sorted(expected & set(cases)):
        case = cases[name]
        arms = _object(case.get("arms"))
        for arm in ("with", "without"):
            runs = _array(arms.get(arm))
            row: dict[str, object] = {"case": name, "arm": arm, "native_complete": False}
            rows.append(row)
            if len(runs) != 1:
                row["issue"] = "Expected exactly one native run per arm"
                continue
            run = _object(runs[0])
            row["native_passed"] = run.get("passed") is True
            if run.get("error") or run.get("skippedPaidGraders"):
                row["issue"] = run.get("error") or "Paid graders were skipped"
                continue
            if len(_array(run.get("graders"))) != len(_array(case.get("graders"))):
                row["issue"] = "Incomplete native grading"
                continue
            try:
                record = _bind_record(name, run, records)
                root, fixture = record.get("root"), record.get("fixture")
                if not isinstance(root, str) or not isinstance(fixture, str):
                    raise TypeError
                hashes: dict[str, str] = {}
                for key, value in _object(record.get("input_sha256")).items():
                    if not isinstance(value, str):
                        raise TypeError
                    hashes[key] = value
                row["root"] = root
                row["native_complete"] = True
                trace = run.get("tracePath")
                if not isinstance(trace, str):
                    raise TypeError
                with _workspace(Path(root), Path(trace)) as workspace:
                    verify(workspace, fixture, hashes)
            except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
                row["artifact_status"] = "FAIL"
                row["issue"] = str(error)
            else:
                row["artifact_status"] = "PASS"
    complete = (
        not issues
        and len(rows) == len(expected) * 2
        and all(row["native_complete"] for row in rows)
    )
    passing = complete and all(
        row.get("native_passed") is True and row.get("artifact_status") == "PASS"
        for row in rows
        if row["arm"] == "with"
    )
    status = "PASS" if passing else "FAIL" if complete else "UNVERIFIED"
    return {"status": status, "expected_cases": len(expected), "issues": issues, "arms": rows}


def main(report_path: Path, directory: Path) -> int:
    """Print an arm-bound result and fail closed on incomplete evidence."""
    report = _object(t.cast("object", json.loads(report_path.read_text(encoding="utf-8"))))
    result = check_report(report, directory)
    print(json.dumps(result, indent=2))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
