"""Fixture-backed tests for the ship gate, release trail, fetch guards, and PDF checks.

Runs offline in temp directories; no network.
"""

# ruff: noqa: S101, INP001, PLR2004, D101, D102, D103, D105
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false

from __future__ import annotations

import contextlib
import io
import json
import socket
import typing as t
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest
import topic  # pyright: ignore[reportImplicitRelativeImport]

REFUSED = "refused"
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
    code, _ = cli(
        "release",
        "--run",
        str(run),
        "--to",
        "the platform team",
        "--audience",
        "private",
        "--offline",
    )
    assert code == 2
    assert not (run / "releases").exists()


def test_offline_release_is_recorded_as_offline(run: Path) -> None:
    code, row = cli(
        "release",
        "--run",
        str(run),
        "--to",
        "the platform team",
        "--audience",
        "private",
        "--offline",
        "--allow-offline",
    )
    assert code == 0, row
    assert row["released"] is True
    assert row["live"] is False


def test_failing_gate_blocks_release(run: Path) -> None:
    next((run / "references" / "raw").iterdir()).write_text("changed\n", encoding="utf-8")
    code, row = cli(
        "release",
        "--run",
        str(run),
        "--to",
        "x",
        "--audience",
        "private",
        "--offline",
        "--allow-offline",
    )
    assert code == 1
    assert row["released"] is False


def released(run: Path) -> list[tuple[str, Path]]:
    return [(run.parents[1].name, run)]


def test_affected_releases_follow_source_changes(run: Path) -> None:
    code, _ = cli(
        "release",
        "--run",
        str(run),
        "--to",
        "the platform team",
        "--audience",
        "private",
        "--offline",
        "--allow-offline",
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

    def __enter__(self) -> FakeResponse:
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


def test_decide_needs_a_release(run: Path) -> None:
    code, _ = cli("decide", "--run", str(run), "--decision", "adopt WAL", "--by", "tech lead")
    assert code == 2
    assert not (run / topic.DECISIONS).exists()


def test_decide_traces_to_the_release(run: Path) -> None:
    _, rel = cli(
        "release",
        "--run",
        str(run),
        "--to",
        "the platform team",
        "--audience",
        "private",
        "--offline",
        "--allow-offline",
    )
    code, row = cli(
        "decide", "--run", str(run), "--decision", "adopt WAL", "--by", "tech lead",
        "--revisit", "a benchmark shows checkpoint stalls",
    )  # fmt: skip
    assert code == 0, row
    assert row["release"] == rel["sha256"]
    assert topic.read_jsonl(run / topic.DECISIONS)[0]["decision"] == "adopt WAL"
    assert (
        cli("decide", "--run", str(run), "--decision", "x", "--by", "y", "--release", "zz")[0] == 2
    )


def test_export_bag_round_trips_and_detects_change(run: Path, tmp_path: Path) -> None:
    bag = tmp_path / "bag.zip"
    code, packed = cli("export", "--run", str(run), "--out", str(bag))
    assert code == 0, packed
    assert cli("export", "--check", str(bag))[1]["ok"] is True

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bag) as src, zipfile.ZipFile(bad, "w") as dst:
        for item in src.infolist():
            body = src.read(item)
            dst.writestr(item, b"tampered\n" if item.filename.endswith("report.md") else body)
    code, result = cli("export", "--check", str(bad))
    assert code == 1
    assert result["ok"] is False
    assert result["changed"]


def test_export_refuses_an_out_path_inside_the_run(run: Path) -> None:
    assert cli("export", "--run", str(run), "--out", str(run / "bag.zip"))[0] == 2


def test_resume_refuses_a_conflicting_audience(run: Path) -> None:
    root = str(run.parents[2])
    code, _ = cli("open", "--root", root, "--topic", "wal", "--resume", "--audience", "public")
    assert code == 2
    code, _ = cli("open", "--root", root, "--topic", "wal", "--resume", "--audience", "private")
    assert code == 0


def test_slop_words_come_from_the_vendored_prose_rules() -> None:
    assert {"leverage", "foster", "harness", "it's worth noting"} <= set(topic.SLOP_WORDS)
    assert "beacon" not in topic.SLOP_WORDS


def test_slop_section_must_parse() -> None:
    with pytest.raises(ValueError, match="no 'Cut these words'"):
        topic.parse_slop_words("## Other\n\nInflation: robust.\n")
    with pytest.raises(ValueError, match="lists no words"):
        topic.parse_slop_words("## Cut these words\n\nNothing here.\n")


def test_connection_pins_to_the_vetted_address(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int]] = []

    def fake_connect(address: tuple[str, int], _timeout: float | None) -> t.NoReturn:
        seen.append(address)
        raise OSError(REFUSED)

    monkeypatch.setattr(socket, "create_connection", fake_connect)
    with pytest.raises(OSError, match=REFUSED):
        topic.connect_vetted("example.org", 443, public, 5)
    assert seen == [("93.184.216.34", 443)]
    with pytest.raises(OSError, match="public address"):
        topic.connect_vetted("example.org", 443, lambda _: ["127.0.0.1"], 5)
    assert len(seen) == 1


def test_fetch_connects_to_the_vetted_address(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int]] = []

    def fake_connect(address: tuple[str, int], _timeout: float | None) -> t.NoReturn:
        seen.append(address)
        raise OSError(REFUSED)

    monkeypatch.setattr(socket, "create_connection", fake_connect)
    assert topic.http_fetch("http://example.org/x", public)[0] == 0
    assert seen == [("93.184.216.34", 80)]


def live(body: bytes = b"Readers do not block writers in WAL mode.\n") -> topic.Fetch:
    def fetch(url: str) -> tuple[int, str, bytes, dict[str, str]]:
        return 200, url, body, {}

    return fetch


def rows(result: topic.Row, key: str) -> list[dict[str, t.Any]]:
    return t.cast("list[dict[str, t.Any]]", result[key])


def nxt(result: topic.Row) -> list[str]:
    return t.cast("list[str]", result["next"])


def refresh(run: Path) -> None:
    """Redo the report pipeline after the run's ledgers changed."""
    assert cli("sources", "--write", "--run", str(run))[0] == 0
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0


def aged(run: Path) -> Path:
    """Move ``run`` to a date before today, as a run from an earlier day."""
    _ = run.parents[1].rename(run.parents[2] / "2026-01-05")
    old = run.parents[2] / "2026-01-05" / run.parent.name / run.name
    index = old / "index.md"
    log = index.read_text(encoding="utf-8").replace(
        f"- {run.parents[1].name}: opened", "- 2026-01-05: opened"
    )
    _ = index.write_text(log, encoding="utf-8")
    return old


def test_sources_table_reads_the_same_offline_and_live(run: Path) -> None:
    assert topic.gate(run, None)["ok"]
    assert topic.gate(run, live())["ok"]
    result = topic.gate(run, None)
    assert result["ok"], (result["sources_table"], result["next"])


def test_release_refuses_a_different_audience(run: Path) -> None:
    code, row = cli(
        "release", "--run", str(run), "--to", "all customers", "--audience", "public",
        "--offline", "--allow-offline",
    )  # fmt: skip
    assert code == 2
    assert "audience is private" in row["error"]
    assert "public reader" in row["error"]
    assert not (run / "releases").exists()


def test_release_and_decision_still_write_to_an_earlier_run(run: Path) -> None:
    old = aged(run)
    code, rel = cli(
        "release", "--run", str(old), "--to", "the platform team", "--audience", "private",
        "--offline", "--allow-offline",
    )  # fmt: skip
    assert code == 0, rel
    assert cli("searched", "--run", str(old), "--query", "q")[0] == 2
    code, _ = cli("decide", "--run", str(old), "--decision", "adopt WAL", "--by", "lead")
    assert code == 0


def test_brief_cites_only_what_the_report_cites(run: Path) -> None:
    _ = (run / "brief.md").write_text(
        "WAL helps readers [S1] and a cache [S2].\n", encoding="utf-8"
    )
    result = topic.gate(run, None)
    assert result["ok"] is False
    assert [f["rule"] for f in rows(result, "brief")] == ["brief-citation"]
    assert "[S2]" in rows(result, "brief")[0]["detail"]
    _ = (run / "brief.md").write_text("WAL helps readers [S1].\n", encoding="utf-8")
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0
    assert topic.gate(run, None)["ok"]


def test_brief_is_scanned_at_the_run_audience(run: Path) -> None:
    text = (
        (run / "index.md")
        .read_text(encoding="utf-8")
        .replace("audience: private", "audience: public")
    )
    _ = (run / "index.md").write_text(text, encoding="utf-8")
    _ = (run / "brief.md").write_text("See https://wiki.acme.internal/x [S1].\n", encoding="utf-8")
    result = topic.gate(run, None)
    assert {(f["file"], f["kind"]) for f in rows(result, "scan")} == {("brief.md", "internal-host")}


def test_failed_search_is_a_gap_until_it_is_retried(run: Path) -> None:
    args = ("searched", "--run", str(run), "--query", "wal on nfs")
    code, row = cli(*args, "--failed", "rate-limit")
    assert (code, row["status"], row["failure"]) == (0, "failed", "rate-limit")
    refresh(run)
    result = topic.gate(run, None)
    assert result["ok"] is False
    assert [g["query"] for g in rows(result, "search_gaps")] == ["wal on nfs"]
    assert [f["rule"] for f in rows(result, "lint")] == ["failed-search"]
    assert cli(*args, "--results", "4")[0] == 0
    refresh(run)
    result = topic.gate(run, None)
    assert result["ok"], result["lint"]
    assert result["search_gaps"] == []


def test_failed_search_listed_under_open_questions_passes(run: Path) -> None:
    assert cli("searched", "--run", str(run), "--query", "wal on nfs", "--failed", "auth")[0] == 0
    text = (run / "report.md").read_text(encoding="utf-8")
    text = text.replace("## Method", "- The search 'wal on nfs' failed on auth.\n\n## Method")
    _ = (run / "report.md").write_text(text, encoding="utf-8")
    refresh(run)
    result = topic.gate(run, None)
    assert result["ok"], result["lint"]
    assert [g["failure"] for g in rows(result, "search_gaps")] == ["auth"]


def test_failed_search_takes_no_result_count(run: Path) -> None:
    code, row = cli(
        "searched", "--run", str(run), "--query", "q", "--failed", "error", "--results", "0"
    )
    assert code == 2
    assert "--failed and --results" in row["error"]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "secret"),
        ("token gho_abcdefghijklmnopqrstuvwxyz0123456789", "secret"),
        ("token github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz", "secret"),
        ("key AKIAABCDEFGHIJKLMNOP", "secret"),
        ("hook xoxb-123456789012-abcdefghij", "secret"),
        ("-----BEGIN RSA PRIVATE KEY-----", "secret"),
    ],
)
def test_secrets_are_flagged_at_every_audience(text: str, kind: str) -> None:
    for audience in topic.AUDIENCES:
        assert [k for _, k, _ in topic.scan_text(text, audience, [])] == [kind]


@pytest.mark.parametrize(
    "text",
    [
        "https://wiki.acme.internal/x",
        "ssh build.corp",
        "nas.lan share",
        "intranet at a.b.intranet",
        "router.home.arpa",
        "http://localhost:3000/",
        "bound to 10.1.2.3",
        "bound to 192.168.0.9",
        "bound to 127.0.0.1",
    ],
)
def test_internal_hosts_are_flagged_only_at_public(text: str) -> None:
    assert [k for _, k, _ in topic.scan_text(text, "public", [])] == ["internal-host"]
    assert topic.scan_text(text, "internal", []) == []


@pytest.mark.parametrize(
    "text",
    [
        "8.8.8.8 and 93.184.216.34",
        "edit settings.local.json",
        "AKIAIOSFODNN7EXAMPLE",
        "a mylocalhost",
    ],
)
def test_scan_leaves_public_addresses_and_file_names_alone(text: str) -> None:
    assert topic.scan_text(text, "public", []) == []


def test_export_refuses_to_overwrite_a_bag(run: Path, tmp_path: Path) -> None:
    bag = tmp_path / "bag.zip"
    assert cli("export", "--run", str(run), "--out", str(bag))[0] == 0
    before = bag.read_bytes()
    code, row = cli("export", "--run", str(run), "--out", str(bag))
    assert code == 2
    assert "bag.zip already exists" in row["error"]
    assert "--out" in row["error"]
    assert bag.read_bytes() == before


def test_export_records_the_zip_digest_and_checks_it(run: Path, tmp_path: Path) -> None:
    bag = tmp_path / "bag.zip"
    code, packed = cli("export", "--run", str(run), "--out", str(bag))
    assert code == 0, packed
    digest = topic.sha256(bag.read_bytes())
    assert packed["sha256"] == digest
    assert topic.read_jsonl(run / topic.EXPORTS)[0]["sha256"] == digest
    assert f"exported bag bag.zip (sha256 {digest[:8]})" in (run / "index.md").read_text(
        encoding="utf-8"
    )
    assert cli("export", "--check", str(bag), "--sha256", digest)[1]["ok"] is True
    code, result = cli("export", "--check", str(bag), "--sha256", "0" * 64)
    assert (code, result["ok"]) == (1, False)


def test_export_percent_encodes_manifest_paths(run: Path, tmp_path: Path) -> None:
    _ = (run / "data").mkdir()
    _ = (run / "data" / "50%.csv").write_text("a,1\n", encoding="utf-8")
    bag = tmp_path / "bag.zip"
    assert cli("export", "--run", str(run), "--out", str(bag))[0] == 0
    with zipfile.ZipFile(bag) as z:
        manifest = z.read(next(n for n in z.namelist() if n.endswith("/manifest-sha256.txt")))
    assert b"  data/data/50%25.csv\n" in manifest
    assert cli("export", "--check", str(bag))[1]["ok"] is True


def test_export_reopens_the_bag_it_wrote(
    run: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_path: Path, _expected: str | None = None) -> topic.Row:
        return {"ok": False, "missing": ["data/x"], "changed": [], "extra": []}

    monkeypatch.setattr(topic, "check_bag", broken)
    bag = tmp_path / "bag.zip"
    code, row = cli("export", "--run", str(run), "--out", str(bag))
    assert code == 2
    assert "failed its own check" in row["error"]
    assert not bag.exists()
    assert not (run / topic.EXPORTS).exists()


def set_audience(run: Path, audience: str, redact: str = "") -> None:
    index = run / "index.md"
    text = index.read_text(encoding="utf-8").replace("audience: private", f"audience: {audience}")
    if redact:
        text = text.replace(f"audience: {audience}\n", f"audience: {audience}\nredact: {redact}\n")
    _ = index.write_text(text, encoding="utf-8")


def test_first_failing_step_follows_the_pipeline_order(run: Path, tmp_path: Path) -> None:
    assert topic.gate(run, None)["first_failing"] is None
    cap = tmp_path / "b.txt"
    _ = cap.write_text("Checkpoints run when the log passes 1000 pages.\n", encoding="utf-8")
    code, _row = cli(
        "add", "--run", str(run), "--url", "https://sqlite.org/pragma.html", "--file", str(cap),
        "--kind", "vendor", "--quote", "checkpoints run",
    )  # fmt: skip
    assert code == 0
    result = topic.gate(run, None)
    assert result["first_failing"] == "sources"
    assert nxt(result)[0].startswith("prepare")

    code, prepared = cli("prepare", "--run", str(run), "--offline")
    assert (code, prepared["sources_table"]) == (0, "written")
    assert prepared["counts"] == {"ok": 2}
    assert topic.gate(run, None)["first_failing"] == "claims"
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0

    next(iter(sorted((run / "references" / "raw").iterdir()))).write_text("x\n", encoding="utf-8")
    result = topic.gate(run, None)
    assert (result["ok"], result["first_failing"]) == (False, "verify")
    assert "sources" in nxt(result)[1]


def test_prepare_needs_a_report_with_a_sources_heading(run: Path) -> None:
    text = (run / "report.md").read_text(encoding="utf-8").replace("## Sources\n", "")
    _ = (run / "report.md").write_text(text, encoding="utf-8")
    code, row = cli("prepare", "--run", str(run), "--offline")
    assert code == 2
    assert "no ## Sources section" in row["error"]
    (run / "report.md").unlink()
    code, row = cli("prepare", "--run", str(run), "--offline")
    assert (code, "no report.md" in row["error"]) == (2, True)


def test_check_counts_what_the_hero_quotes(run: Path) -> None:
    counts = topic.gate(run, None)["counts"]
    assert counts == {
        "findings": 1, "sources": 1, "carried": 0, "states": {"intact": 1},
        "open_questions": 1, "open_in_index": 0, "open_in_report": 1,
        "failed_sources": 0, "open_items": 1, "ticked": 0,
    }  # fmt: skip


def test_open_questions_merge_the_index_and_the_report(run: Path) -> None:
    index = run / "index.md"
    text = index.read_text(encoding="utf-8").replace(
        "- [ ] \n", "- [ ] Does a long checkpoint stall readers?\n- [ ] Is it safe on SMB?\n"
    )
    _ = index.write_text(text, encoding="utf-8")
    counts = t.cast("dict[str, int]", topic.gate(run, None)["counts"])
    assert (counts["open_in_index"], counts["open_in_report"], counts["open_questions"]) == (
        2,
        1,
        2,
    )


def test_the_brief_is_listed_and_reviewed_with_the_report(run: Path) -> None:
    _ = (run / "brief.md").write_text("Readers never wait for writers [S1].\n", encoding="utf-8")
    result = topic.gate(run, None)
    assert (result["ok"], result["first_failing"]) == (False, "claims")
    code, out = cli("claims", "--reviewed", str(run / "report.md"))
    assert code == 0
    assert [(r["from"], r["cites"]) for r in out["brief"]] == [("brief.md", ["S1"])]
    assert out["quotes"]["S1"] == ["readers do not block writers"]
    assert topic.gate(run, None)["ok"]
    _ = (run / "brief.md").write_text("Readers always wait for writers [S1].\n", encoding="utf-8")
    assert topic.gate(run, None)["first_failing"] == "claims"


def test_a_public_run_needs_a_redact_decision(run: Path) -> None:
    set_audience(run, "public")
    result = topic.gate(run, None)
    assert (result["ok"], result["first_failing"], result["redact_decision"]) == (
        False, "redact", "missing",
    )  # fmt: skip
    assert "redact" in nxt(result)[0]
    args = ("release", "--run", str(run), "--to", "readers", "--audience", "public")
    code, row = cli(*args, "--offline", "--allow-offline")
    assert (code, row["released"]) == (1, False)
    for decision in ("[]", '["Acme Corp"]'):
        set_audience(run, "public")
        text = (run / "index.md").read_text(encoding="utf-8")
        text = "\n".join(ln for ln in text.split("\n") if not ln.startswith("redact:"))
        _ = (run / "index.md").write_text(
            text.replace("audience: public\n", f"audience: public\nredact: {decision}\n"),
            encoding="utf-8",
        )
        result = topic.gate(run, None)
        assert result["ok"], (decision, result["next"])
        assert result["redact_decision"] == "recorded"
    code, row = cli(*args, "--offline", "--allow-offline")
    assert (code, row["released"]) == (0, True)


def test_a_private_run_needs_no_redact_decision(run: Path) -> None:
    assert topic.gate(run, None)["redact_decision"] == "not needed"


def test_brief_may_not_add_an_uncited_claim(run: Path) -> None:
    brief = run / "brief.md"
    claim = "Readers do not block writers in WAL mode, so a read-heavy service keeps its latency"
    _ = brief.write_text(
        f"# WAL suits reads\n\n{claim} while writes continue.\n\nFull report: [r](report.md)\n",
        encoding="utf-8",
    )
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0
    assert topic.gate(run, None)["ok"]
    _ = brief.write_text(
        "# WAL suits reads\n\nWAL also halves disk usage for every deployment.\n", encoding="utf-8"
    )
    assert cli("claims", "--reviewed", str(run / "report.md"))[0] == 0
    result = topic.gate(run, None)
    assert [f["rule"] for f in rows(result, "brief")] == ["brief-new-claim"]
    assert "halves disk usage" in rows(result, "brief")[0]["detail"]
    assert result["first_failing"] == "lint"
