#!/usr/bin/env python3
"""Render, measure, and preserve goal handoffs without activating them.

Every command emits JSON. ``render --input draft.json --save`` publishes a
revision; omitting ``--save`` never writes. ``check`` verifies a saved bundle.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

_DEFAULT_LIMIT = 3800
_HOST_LIMIT = 4000
_PLACEHOLDER = "{{GOAL_SPEC}}"
_TOPIC = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_REFERENCE = re.compile(r"Goal specification: <([^<>\r\n]+)> \(sha256:([0-9a-f]{64})\)")
_PREDECESSOR = re.compile(r"\n\nPrevious goal: <([^<>\r\n]+)>\Z")
_HEADER = "<!-- goal-planner "
_MAX_TOPIC_LENGTH = 80
_REVISION_WIDTH = 3
_SURROGATE_START = 0xD800
_SURROGATE_END = 0xDFFF


class PlannerError(ValueError):
    """Reject an ambiguous, unsafe, or incomplete handoff."""


def _fail(message: str) -> NoReturn:
    raise PlannerError(message)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"{label} must be a JSON object")
    if any(not isinstance(key, str) for key in cast("dict[object, object]", value)):
        _fail(f"{label} must be a JSON object")
    return cast("dict[str, object]", value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} must be a nonempty string")
    if "\x00" in value or any(_SURROGATE_START <= ord(char) <= _SURROGATE_END for char in value):
        _fail(f"{label} contains a NUL or unpaired surrogate")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{label} must be a boolean")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        _fail(f"{label} must be a positive integer")
    return value


def _keys(value: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = sorted(value.keys() - allowed)
    if unknown:
        _fail(f"Unknown {label} fields: {', '.join(unknown)}")


def _read_json(path: str) -> dict[str, object]:
    source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return _object(json.loads(source), "input")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _safe_path(value: str | Path) -> Path:
    path = Path(value).expanduser().absolute()
    if ".." in path.parts or any(char in str(path) for char in "<>\r\n\x00"):
        _fail("Paths cannot contain traversal, angle brackets, or control characters")
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            _fail(f"Symlink path is not allowed: {part}")
    return path


def _mkdir(path: Path) -> None:
    _safe_path(path)
    path.mkdir(parents=True, exist_ok=True)
    _safe_path(path)


def _text(path: Path) -> str:
    _safe_path(path)
    if not path.is_file():
        _fail(f"Required regular file is missing: {path}")
    return path.read_bytes().decode("utf-8")


def _publish(path: Path, content: str, *, replace: bool = False) -> None:
    """Publish complete bytes; replacement is reserved for approved settings updates."""
    _safe_path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".goal-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(path)
        if replace:
            Path(temporary).replace(path)
        else:
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def budget(host: str, maximum: int | None, spend_reserve: bool, strict: bool) -> int | None:
    """Return the drafting ceiling without implicitly spending Claude's reserve."""
    if host not in {"claude", "codex"}:
        _fail("host must be claude or codex")
    if maximum is not None:
        _integer(maximum, "max_chars")
    if host == "codex":
        if spend_reserve or strict:
            _fail("Claude reserve flags do not apply to Codex")
        return maximum
    ceiling = _HOST_LIMIT - int(strict) if spend_reserve else _DEFAULT_LIMIT
    return min(maximum, ceiling) if maximum is not None else ceiling


def measure(payload: str, host: str, limit: int | None) -> dict[str, object]:
    """Count both Unicode conventions, including the complete copyable payload."""
    _string(payload, "payload")
    condition = payload.removeprefix("/goal ")
    points = len(payload)
    units = len(payload.encode("utf-16-le")) // 2
    return {
        "payload": {"codepoints": points, "utf16": units},
        "condition": {
            "codepoints": len(condition),
            "utf16": len(condition.encode("utf-16-le")) // 2,
        },
        "limit": limit,
        "within_limit": limit is None or max(points, units) <= limit,
        "remaining_budget": None if limit is None else limit - max(points, units),
        "remaining_host_capacity": _HOST_LIMIT - max(points, units) if host == "claude" else None,
    }


@dataclass(frozen=True)
class Draft:
    """A validated authored contract, without semantic inference."""

    host: str
    topic: str
    body: str
    specification: str | None
    root: Path
    date: str
    limit: int | None
    predecessors: tuple[Path, ...]

    @property
    def identity(self) -> str:
        """Identify authored content independently of its revision and date."""
        return _digest(_json({"body": self.body, "specification": self.specification}))


def parse_request(value: dict[str, object]) -> Draft:
    """Validate a request without reading profiles or inferring permissions."""
    _keys(
        value,
        {
            "host",
            "topic",
            "body",
            "specification",
            "documents_root",
            "date",
            "max_chars",
            "spend_reserve",
            "strict_less_than_4000",
            "predecessors",
        },
        "request",
    )
    host = _string(value.get("host"), "host")
    topic = _string(value.get("topic"), "topic")
    if not _TOPIC.fullmatch(topic) or len(topic) > _MAX_TOPIC_LENGTH:
        _fail("topic must be a lowercase hyphenated slug of at most 80 characters")
    body = _string(value.get("body"), "body")
    if body.startswith("/goal ") or _REFERENCE.search(body) or _PREDECESSOR.search(body):
        _fail("body must omit /goal and generated specification/predecessor references")
    specification = value.get("specification")
    spec = None if specification is None else _string(specification, "specification")
    if body.count(_PLACEHOLDER) != int(spec is not None):
        _fail("A specification requires exactly one {{GOAL_SPEC}} token; omit it otherwise")
    local_date = dt.datetime.now(dt.UTC).astimezone().date().isoformat()
    date = _string(value.get("date", local_date), "date")
    if not _DATE.fullmatch(date):
        _fail("date must use YYYY-MM-DD")
    dt.date.fromisoformat(date)
    raw_previous = value.get("predecessors", [])
    if not isinstance(raw_previous, list):
        _fail("predecessors must be an array of explicit saved goal paths")
    predecessors = tuple(
        _safe_path(_string(item, "predecessor")) for item in cast("list[object]", raw_previous)
    )
    raw_maximum = value.get("max_chars")
    maximum = None if raw_maximum is None else _integer(raw_maximum, "max_chars")
    limit = budget(
        host,
        maximum,
        _boolean(value.get("spend_reserve", False), "spend_reserve"),
        _boolean(value.get("strict_less_than_4000", False), "strict_less_than_4000"),
    )
    root = _safe_path(_string(value.get("documents_root", "~/Documents"), "documents_root"))
    return Draft(host, topic, body, spec, root, date, limit, predecessors)


@dataclass(frozen=True)
class Artifact:
    """A verified saved goal and optional specification."""

    revision: int
    path: Path
    payload: str
    specification: Path | None
    identity: str
    relocated: bool = False


def _revision(path: Path, topic: str) -> int:
    match = re.fullmatch(re.escape(topic) + r"-([0-9]{3,})\.md", path.name)
    if match is None or int(match[1]) < 1:
        _fail(f"Unrecognized revision filename: {path.name}")
    return int(match[1])


def _reservation(root: Path, topic: str, revision: int) -> Path:
    return root / ".goal-reservations" / f"{topic}-{revision:03}.reservation"


def inspect_goal(
    path: Path,
    topic: str | None = None,
    *,
    allow_relocation: bool = False,
) -> Artifact:
    """Verify the exact companion location, digest, identity, and complete pair."""
    path = _safe_path(path)
    if path.parent.name != "goals" or not _DATE.fullmatch(path.parent.parent.name):
        _fail("Saved goals must be under YYYY-MM-DD/goals")
    dt.date.fromisoformat(path.parent.parent.name)
    if topic is None:
        match = re.fullmatch(r"(.+)-[0-9]{3,}\.md", path.name)
        if match is None:
            _fail("Cannot identify the saved goal topic")
        topic = _string(match[1], "saved goal topic")
    if not _TOPIC.fullmatch(topic):
        _fail("Invalid saved goal topic")
    revision = _revision(path, topic)
    relocated = False
    payload = _text(path)
    if not payload.startswith("/goal ") or not payload[6:].strip() or _PLACEHOLDER in payload:
        _fail(f"Foreign or incomplete goal file: {path}")
    body = _PREDECESSOR.sub("", payload[6:])
    references = list(_REFERENCE.finditer(body))
    spec_path = path.parent.parent / "goal-specs" / path.name
    if not references:
        if spec_path.exists() or spec_path.is_symlink():
            _fail(f"Unexpected companion without a goal reference: {spec_path}")
        identity = _digest(_json({"body": body, "specification": None}))
        return Artifact(revision, path, payload, None, identity, relocated)
    if len(references) != 1:
        _fail("Goal must reference exactly one specification")
    reference = references[0]
    referenced = _safe_path(reference[1])
    if referenced != spec_path:
        if not allow_relocation or referenced.parts[-3:] != spec_path.parts[-3:]:
            _fail("Companion locator does not match this goal's dated topic/revision")
        relocated = True
    specification = _text(spec_path)
    if _digest(specification) != reference[2]:
        _fail("Companion digest changed; reconcile the contract before rendering again")
    header, separator, full_contract = specification.partition("\n")
    if not separator or not header.startswith(_HEADER) or not header.endswith(" -->"):
        _fail("Companion identity header is missing")
    metadata = _object(json.loads(header[len(_HEADER) : -4]), "specification metadata")
    if metadata.get("schema_version") != 1 or metadata.get("topic") != topic:
        _fail("Companion topic/schema identity mismatch")
    if metadata.get("revision") != revision:
        _fail("Companion revision identity mismatch")
    previous = _PREDECESSOR.search(payload[6:])
    if metadata.get("predecessor") != (previous[1] if previous else None):
        _fail("Companion predecessor identity mismatch")
    identity = _digest(
        _json(
            {
                "body": _REFERENCE.sub(_PLACEHOLDER, body),
                "specification": full_contract,
            }
        )
    )
    if metadata.get("draft_sha256") != identity:
        _fail("Companion authored-content identity mismatch")
    return Artifact(revision, path, payload, spec_path, identity, relocated)


def _dated_roots(root: Path) -> Iterator[Path]:
    for path in root.iterdir():
        if not _DATE.fullmatch(path.name):
            continue
        try:
            dt.date.fromisoformat(path.name)
        except ValueError:
            continue
        yield _safe_path(path)


def _inventory(draft: Draft) -> tuple[list[Artifact], set[int], list[str]]:
    paths: set[Path] = set(draft.predecessors)
    used: set[int] = set()
    claims: dict[int, Path] = {}
    incomplete: list[str] = []
    reservations = draft.root / ".goal-reservations"
    _safe_path(reservations)
    if reservations.exists():
        for item in reservations.glob(f"{draft.topic}-*.reservation"):
            _safe_path(item)
            match = re.fullmatch(re.escape(draft.topic) + r"-([0-9]+)\.reservation", item.name)
            if match is None:
                continue
            if not item.is_dir() or len(match[1]) < _REVISION_WIDTH or int(match[1]) < 1:
                _fail(f"Foreign reservation: {item}")
            revision = int(match[1])
            used.add(revision)
            claims[revision] = item
    if draft.root.exists():
        for date_path in _dated_roots(draft.root):
            for folder in ("goals", "goal-specs"):
                directory = _safe_path(date_path / folder)
                if not directory.exists():
                    continue
                for path in directory.glob(f"{draft.topic}-*.md"):
                    if not re.fullmatch(re.escape(draft.topic) + r"-[0-9]+\.md", path.name):
                        continue
                    _safe_path(path)
                    revision = _revision(path, draft.topic)
                    used.add(revision)
                    goal = date_path / "goals" / path.name
                    if goal.is_file():
                        paths.add(goal)
                    else:
                        incomplete.append(str(path))
    artifacts: dict[int, Artifact] = {}
    for path in sorted(paths):
        artifact = inspect_goal(path, draft.topic, allow_relocation=True)
        if artifact.revision in artifacts and artifacts[artifact.revision].path != path:
            _fail(f"Conflicting revision {artifact.revision}; reconcile imported/local lineages")
        artifacts[artifact.revision] = artifact
        used.add(artifact.revision)
    completed = {
        revision
        for revision, artifact in artifacts.items()
        if artifact.path.parents[2] == draft.root
    }
    incomplete.extend(str(path) for revision, path in claims.items() if revision not in completed)
    return sorted(artifacts.values(), key=lambda item: item.revision), used, incomplete


def _candidate(draft: Draft, revision: int, previous: Path | None) -> tuple[str, str | None]:
    body = draft.body
    specification = None
    if draft.specification is not None:
        metadata = {
            "schema_version": 1,
            "topic": draft.topic,
            "revision": revision,
            "predecessor": str(previous) if previous else None,
            "draft_sha256": draft.identity,
        }
        specification = _HEADER + _json(metadata) + " -->\n" + draft.specification
        path = draft.root / draft.date / "goal-specs" / f"{draft.topic}-{revision:03}.md"
        body = body.replace(
            _PLACEHOLDER, f"Goal specification: <{path}> (sha256:{_digest(specification)})"
        )
    if previous is not None:
        body += f"\n\nPrevious goal: <{previous}>"
    return "/goal " + body, specification


def _result(draft: Draft, payload: str, revision: int, incomplete: list[str]) -> dict[str, object]:
    counts = measure(payload, draft.host, draft.limit)
    return {
        "payload": payload,
        "measurements": counts,
        "requested_date": draft.date,
        "revision": revision,
        "goal_path": None,
        "spec_path": None,
        "reused": False,
        "ready": counts["within_limit"] and draft.specification is None,
        "incomplete_revisions": incomplete,
        "errors": [],
    }


def render(draft: Draft, *, save: bool = False) -> dict[str, object]:
    """Render a draft and optionally save an immutable revision."""
    while True:
        artifacts, used, incomplete = _inventory(draft)
        if (
            artifacts
            and artifacts[-1].identity == draft.identity
            and artifacts[-1].path.parents[2] == draft.root
            and not artifacts[-1].relocated
        ):
            artifact = artifacts[-1]
            result = _result(draft, artifact.payload, artifact.revision, incomplete)
            result.update(
                {
                    "goal_path": str(artifact.path),
                    "spec_path": str(artifact.specification) if artifact.specification else None,
                    "reused": True,
                }
            )
            counts = cast("dict[str, object]", result["measurements"])
            result["ready"] = counts["within_limit"]
            return result
        previous = artifacts[-1].path if artifacts else None
        revision = max(used, default=0) + 1
        payload, specification = _candidate(draft, revision, previous)
        result = _result(draft, payload, revision, incomplete)
        counts = cast("dict[str, object]", result["measurements"])
        if not counts["within_limit"]:
            result["errors"] = [
                "Payload exceeds the drafting budget; shorten it without losing requirements"
            ]
            return result
        if not save:
            return result
        try:
            reservations = draft.root / ".goal-reservations"
            _mkdir(reservations)
            reservation = _reservation(draft.root, draft.topic, revision)
            _safe_path(reservation)
            try:
                reservation.mkdir()
            except FileExistsError:
                continue
            goal_path = draft.root / draft.date / "goals" / f"{draft.topic}-{revision:03}.md"
            spec_path = draft.root / draft.date / "goal-specs" / goal_path.name
            if goal_path.exists() or spec_path.exists():
                _fail("Revision destination appeared after allocation; inspect the preserved files")
            _mkdir(goal_path.parent)
            if specification is not None:
                _mkdir(spec_path.parent)
                _publish(spec_path, specification)
            _publish(goal_path, payload)
            artifact = inspect_goal(goal_path, draft.topic)
            if artifact.payload != payload:
                _fail("Saved and printed goal bytes differ")
            result.update(
                {
                    "goal_path": str(goal_path),
                    "spec_path": str(spec_path) if specification is not None else None,
                    "ready": True,
                }
            )
        except (OSError, ValueError) as error:
            result["ready"] = False
            result["errors"] = [str(error)]
        return result


def validate_settings(value: dict[str, object], kind: str) -> dict[str, object]:
    """Validate explicitly approved portable defaults or separate machine bindings."""
    shared = {"schema_version", "kind", "approved"}
    _keys(
        value,
        shared | ({"name", "defaults", "principles"} if kind == "profile" else {"documents_root"}),
        kind,
    )
    if value.get("schema_version") != 1 or value.get("kind") != kind:
        _fail(f"Expected schema_version 1 and kind {kind}")
    if value.get("approved") is not True:
        _fail("Settings must record explicit approval with approved: true")
    if kind == "bindings":
        root = _string(value.get("documents_root"), "documents_root")
        if not Path(root).is_absolute() and not root.startswith("~/"):
            _fail("Persistent documents_root must be absolute or start with ~/")
        _safe_path(root)
        return value
    _string(value.get("name"), "name")
    defaults = _object(value.get("defaults"), "defaults")
    _keys(defaults, {"host", "save", "max_chars"}, "profile defaults")
    host = _string(defaults.get("host"), "defaults.host")
    _boolean(defaults.get("save"), "defaults.save")
    raw_maximum = defaults.get("max_chars")
    maximum = None if raw_maximum is None else _integer(raw_maximum, "defaults.max_chars")
    limit = budget(host, maximum, spend_reserve=False, strict=False)
    if maximum is not None and limit != maximum:
        _fail("Profile defaults cannot spend Claude's addendum reserve")
    principles = value.get("principles")
    if not isinstance(principles, list):
        _fail("principles must be an array of approved text")
    for principle in cast("list[object]", principles):
        _string(principle, "principle")
    return value


def save_settings(path: Path, value: dict[str, object], *, approved: bool, replace: bool) -> None:
    """Persist reviewed settings only with an explicit approval argument."""
    if not approved:
        _fail("Writing settings requires --approved after user approval")
    path = _safe_path(path)
    kind = _string(value.get("kind"), "kind")
    if kind not in {"profile", "bindings"}:
        _fail("Settings kind must be profile or bindings")
    validate_settings(value, kind)
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    existing = path.exists()
    if existing:
        if not replace:
            _fail("Settings already exist; use --replace for an approved update")
        validate_settings(_object(json.loads(_text(path)), "existing settings"), kind)
    _mkdir(path.parent)
    _publish(path, content, replace=replace and existing)


def _limits(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True, choices=("claude", "codex"))
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--spend-reserve", action="store_true")
    parser.add_argument("--strict-less-than-4000", action="store_true")


def main(argv: list[str] | None = None) -> int:
    """Run the JSON CLI without host activation or implicit settings discovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("--input", required=True)
    render_parser.add_argument("--save", action="store_true")
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--goal", required=True)
    _limits(check_parser)
    count_parser = commands.add_parser("count")
    count_parser.add_argument("--input", required=True)
    _limits(count_parser)
    for kind in ("profile", "bindings"):
        settings = commands.add_parser(kind).add_subparsers(dest="operation", required=True)
        settings.add_parser("read").add_argument("--path", required=True)
        write = settings.add_parser("write")
        write.add_argument("--path", required=True)
        write.add_argument("--input", required=True)
        write.add_argument("--approved", action="store_true")
        write.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            result = render(parse_request(_read_json(args.input)), save=args.save)
        elif args.command in {"count", "check"}:
            limit = budget(
                args.host, args.max_chars, args.spend_reserve, args.strict_less_than_4000
            )
            if args.command == "check":
                artifact = inspect_goal(Path(args.goal))
                payload = artifact.payload
            else:
                payload = sys.stdin.read() if args.input == "-" else _text(Path(args.input))
            counts = measure(payload, args.host, limit)
            result = {"payload": payload, "measurements": counts, "ready": counts["within_limit"]}
        elif args.operation == "read":
            result = validate_settings(_read_json(str(_safe_path(args.path))), args.command)
        else:
            result = _read_json(args.input)
            if result.get("kind") != args.command:
                _fail(f"Expected kind {args.command}")
            save_settings(Path(args.path), result, approved=args.approved, replace=args.replace)
        print(_json(result))
        return 0 if result.get("ready", True) and not result.get("errors") else 2
    except (OSError, ValueError) as error:
        print(_json({"ready": False, "errors": [str(error)]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
