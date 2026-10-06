"""Fixture-backed tests for the ship gate, release trail, fetch guards, and PDF checks.

Runs offline in temp directories; no network.
"""

# ruff: noqa: S101, INP001, PLR2004, D101, D102, D103, D105
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false

from __future__ import annotations

import contextlib
import io
import json
import typing as t
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import topic  # pyright: ignore[reportImplicitRelativeImport]

REPORT = """\
# WAL lets readers proceed during writes

{date} · research/wal · research · private

## Summary

Readers do not block writers in WAL mode, so a read-heavy service keeps its
latency while writes continue. Confidence is medium.

## Findings

### Readers proceed while a writer appends

Readers do not block writers in WAL mode [S1]. Confidence: medium, one vendor source.

## Open questions

- Does a long checkpoint stall readers? A benchmark would settle it.

## Method

Read the vendor documentation page.

## Sources
"""


def cli(*argv: str) -> tuple[int, t.Any]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = topic.main(list(argv))
    text = out.getvalue()
    try:
        return code, json.loads(text)
    except ValueError:
        return code, text


@pytest.fixture
def run(tmp_path: Path) -> Path:
    """Build a run with a captured source and a report that passes the gate."""
    root = tmp_path / "root"
    _, opened = cli("open", "--root", str(root), "--topic", "wal", "--subject", "SQLite WAL")
    run = Path(opened["run_dir"])
    cap = tmp_path / "wal.txt"
    _ = cap.write_text("Readers do not block writers in WAL mode.\n", encoding="utf-8")
    code, _ = cli(
        "add", "--run", str(run), "--url", "https://sqlite.org/wal.html", "--file", str(cap),
        "--kind", "vendor", "--title", "Write-Ahead Logging", "--author", "SQLite",
        "--quote", "readers do not block writers",
    )  # fmt: skip
    assert code == 0
    _ = (run / "report.md").write_text(
        REPORT.replace("{date}", run.parents[1].name), encoding="utf-8"
    )
    assert cli("verify", "--offline", "--run", str(run))[0] == 0
    assert cli("sources", "--write", "--run", str(run))[0] == 0
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0
    return run


def test_gate_passes_offline(run: Path) -> None:
    result = topic.gate(run, None)
    assert result["ok"], (
        result["lint"],
        result["scan"],
        result["sources"],
        result["sources_table"],
    )
    assert result["live"] is False
    assert result["next"] == []


def test_gate_fails_on_altered_capture(run: Path) -> None:
    cap = next((run / "references" / "raw").iterdir())
    _ = cap.write_text("Readers block writers.\n", encoding="utf-8")
    result = topic.gate(run, None)
    assert result["ok"] is False
    failures = t.cast("dict[str, list[dict[str, str]]]", result["sources"])["failures"]
    assert failures[0]["status"] == "changed"


def test_gate_fails_on_stale_sources_table(run: Path) -> None:
    text = (run / "report.md").read_text(encoding="utf-8")
    _ = (run / "report.md").write_text(text + "\nextra row\n", encoding="utf-8")
    result = topic.gate(run, None)
    assert result["ok"] is False
    assert result["sources_table"] == "stale"


def test_gate_needs_a_report(run: Path) -> None:
    (run / "report.md").unlink()
    with pytest.raises(ValueError, match=r"no report\.md"):
        topic.gate(run, None)


def test_offline_release_is_refused_without_the_flag(run: Path) -> None:
    code, _ = cli("release", "--run", str(run), "--to", "the platform team", "--offline")
    assert code == 2
    assert not (run / "releases").exists()


def test_offline_release_is_recorded_as_offline(run: Path) -> None:
    code, row = cli(
        "release", "--run", str(run), "--to", "the platform team", "--offline", "--allow-offline"
    )
    assert code == 0, row
    assert row["released"] is True
    assert row["live"] is False


def test_failing_gate_blocks_release(run: Path) -> None:
    next((run / "references" / "raw").iterdir()).write_text("changed\n", encoding="utf-8")
    code, row = cli("release", "--run", str(run), "--to", "x", "--offline", "--allow-offline")
    assert code == 1
    assert row["released"] is False


def released(run: Path) -> list[tuple[str, Path]]:
    return [(run.parents[1].name, run)]


def test_affected_releases_follow_source_changes(run: Path) -> None:
    code, _ = cli(
        "release", "--run", str(run), "--to", "the platform team", "--offline", "--allow-offline"
    )
    assert code == 0
    states = {"S1": "intact"}
    assert topic.affected_releases(released(run), run, states) == []

    moved = topic.affected_releases(released(run), run, {"S1": "changed"})
    assert [m["to"] for m in moved] == ["the platform team"]
    assert moved[0]["sources"] == ["S1"]

    rows = topic.read_jsonl(run / topic.MANIFEST)
    topic.append_jsonl(run / topic.MANIFEST, [{**rows[-1], "sha256": "0" * 64, "ref": "9"}])
    assert topic.affected_releases(released(run), run, states)[0]["sources"] == ["S1"]


def test_pdf_quotes_are_unverifiable(run: Path) -> None:
    rows = topic.read_jsonl(run / topic.MANIFEST)
    cap = run / "references" / str(rows[-1]["file"])
    pdf = cap.with_suffix(".pdf")
    _ = cap.rename(pdf)
    row = {**rows[-1], "file": pdf.relative_to(run / "references").as_posix()}
    status, detail, _data = topic.check_capture(run, row)
    assert status == "unverifiable"
    assert "PDF" in detail


def public(_: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "192.168.0.9"]
)
def test_fetch_refuses_non_public_addresses(address: str) -> None:
    status, _, body, _ = topic.http_fetch("http://example.org/x", lambda _: [address])
    assert (status, body) == (0, b"")


def test_fetch_refuses_unresolvable_host() -> None:
    assert topic.http_fetch("https://nowhere.invalid/", lambda _: [])[0] == 0


@t.final
class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.status: int = 200
        self.url: str = "https://example.org/x"
        self.headers: dict[str, str] = {}

    def read(self, n: int = -1) -> bytes:
        return self.body if n < 0 else self.body[:n]

    def __enter__(self) -> t.Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def serve(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    def fake_open(*_args: object, **_kwargs: object) -> FakeResponse:
        return FakeResponse(body)

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)


def test_fetch_caps_body_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(topic, "MAX_FETCH_BYTES", 8)
    serve(monkeypatch, b"x" * 9)
    assert topic.http_fetch("https://example.org/x", public)[0] == 0
    serve(monkeypatch, b"x" * 8)
    status, _, body, _ = topic.http_fetch("https://example.org/x", public)
    assert (status, body) == (200, b"x" * 8)


def test_redirect_to_private_address_is_refused() -> None:
    handler = topic.PublicRedirects(lambda _: ["127.0.0.1"])
    req = urllib.request.Request("https://example.org/x")
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(
            req, io.BytesIO(), 302, "Found", t.cast("t.Any", {}), "http://internal/"
        )
