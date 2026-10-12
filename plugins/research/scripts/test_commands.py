"""Tests for the run ledgers and the commands that write them: past runs, page text, carry, status.

Runs offline in temp directories; fetches are stubs.
"""

# ruff: noqa: S101, INP001, PLR2004, D103
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false

from __future__ import annotations

import contextlib
import getpass
import io
import json
import sys
import tempfile
import typing as t
from datetime import date, timedelta
from pathlib import Path

import pytest
import topic  # pyright: ignore[reportImplicitRelativeImport]

PAST = "2026-01-05"
TXT = "Readers do not block writers in WAL mode.\n"
BODY = TXT.encode()
LINKS = "See https://e.example/x?a=1;touch${IFS}Z and https://e.example/`id` for more.\n"


def cli(*argv: str) -> tuple[int, t.Any]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = topic.main(list(argv))
    try:
        return code, json.loads(out.getvalue())
    except ValueError:
        return code, out.getvalue()


def call(fn: t.Callable[..., int], fetch: topic.Fetch, *argv: str) -> tuple[int, t.Any]:
    args = topic.build_parser().parse_args(list(argv), namespace=topic.Args())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = fn(args, fetch=fetch)
        except ValueError as e:
            return 2, {"error": str(e)}
    return code, json.loads(out.getvalue())


def stub(status: int = 200, body: bytes = BODY, final: str = "") -> topic.Fetch:
    def fetch(url: str) -> tuple[int, str, bytes, dict[str, str]]:
        return status, final or url, body, {"Content-Type": "text/plain"}

    return fetch


def new_run(root: Path, name: str = "wal", *extra: str) -> Path:
    code, opened = cli("open", "--root", str(root), "--topic", name, *extra)
    assert code == 0, opened
    return Path(opened["run_dir"])


def earlier_day(root: Path, name: str) -> Path:
    """Build a run opened on an earlier day: its log carries no stamp for today."""
    run = new_run(root, name, "--date", PAST)
    index = run / "index.md"
    stamp = f"- {date.today().isoformat()}: opened"  # noqa: DTZ011
    _ = index.write_text(
        index.read_text(encoding="utf-8").replace(stamp, f"- {PAST}: opened"), encoding="utf-8"
    )
    return run


def capture(tmp_path: Path, text: str = TXT) -> str:
    path = tmp_path / "cap.txt"
    _ = path.write_text(text, encoding="utf-8")
    return str(path)


def add(run: Path, *argv: str) -> tuple[int, t.Any]:
    return cli("add", "--run", str(run), *argv)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "root"


def test_a_backdated_run_opened_today_takes_evidence_the_same_day(root: Path) -> None:
    run = new_run(root, "backfill", "--date", PAST)
    assert add(run, "--url", "https://a.example/x", "--unretrieved", "paywall")[0] == 0


def test_a_run_opened_on_an_earlier_day_takes_no_new_evidence(root: Path, tmp_path: Path) -> None:
    old = earlier_day(root, "old")
    _ = (old / "report.md").write_text("# T\n\n## Sources\n", encoding="utf-8")
    _ = (tmp_path / "t.csv").write_text("name,rating\nA,strong\n", encoding="utf-8")
    writes = {
        "add": ["add", "--url", "https://a.example/x", "--unretrieved", "paywall"],
        "run": ["run", "--name", "b", "--", sys.executable, "-c", "pass"],
        "searched": ["searched", "--query", "q"],
        "conflict": ["conflict", "--about", "x", "--source", "S1", "--source", "S2"],
        "sources --write": ["sources", "--write"],
    }
    for name, argv in writes.items():
        code, row = cli(argv[0], "--run", str(old), *argv[1:])
        assert code == 2, name
        assert f"is dated {PAST}, before today" in row["error"], name
    code, row = cli("claims", "--reviewed", str(old / "report.md"))
    assert code == 2
    assert "before today" in row["error"]
    code, row = cli("chart", "--csv", str(tmp_path / "t.csv"), "--out", str(old / "c" / "t.svg"))
    assert code == 2
    assert "before today" in row["error"]
    assert not (old / "references" / "sources.jsonl").exists()
    assert not (old / "data").exists()
    assert not (old / "references" / "searches.jsonl").exists()
    assert not (old / "c").exists()


def test_open_resume_reopens_an_earlier_run_for_today(root: Path) -> None:
    old = earlier_day(root, "old")
    assert add(old, "--url", "https://a.example/x", "--unretrieved", "paywall")[0] == 2
    code, opened = cli("open", "--root", str(root), "--topic", "old", "--resume")
    assert (code, opened["resumed"]) == (0, True)
    assert add(old, "--url", "https://a.example/x", "--unretrieved", "paywall")[0] == 0


def test_page_text_goes_in_a_file_not_the_command_line(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    page = "use $(touch PWNED) to start the `server`"
    fields = tmp_path / "fields.json"
    _ = fields.write_text(
        json.dumps({"quote": [page, "second"], "title": "T $(id)", "author": "A"}), encoding="utf-8"
    )
    cap = capture(tmp_path, f"{page}\nsecond line\n")
    code, row = add(run, "--url", "https://a.example/x", "--file", cap, "--fields", str(fields))
    assert code == 0, row
    assert row["quotes"] == [page, "second"]
    assert (row["title"], row["author"]) == ("T $(id)", "A")
    again = tmp_path / "again.json"
    _ = again.write_text(json.dumps({"title": "other"}), encoding="utf-8")
    code, row = add(run, "--url", "https://a.example/y", "--title", "x", "--fields", str(again))
    assert code == 2
    assert "'title' is also given as --title" in row["error"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ('{"url": "https://a.example/x"}', "'url' is not a field of add"),
        ('{"quote": 3}', "'quote' must be a string or a list of strings"),
        ('["quote"]', "expected a JSON object"),
        ("{", "cannot read it as JSON"),
    ],
)
def test_fields_file_refusals_name_the_reason(
    root: Path, tmp_path: Path, content: str, reason: str
) -> None:
    run = new_run(root)
    fields = tmp_path / "fields.json"
    _ = fields.write_text(content, encoding="utf-8")
    code, row = add(
        run, "--url", "https://a.example/x", "--unretrieved", "x", "--fields", str(fields)
    )
    assert code == 2
    assert reason in row["error"]


def test_searched_reads_its_query_from_a_file(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    fields = tmp_path / "q.json"
    _ = fields.write_text(json.dumps({"query": 'wal "$(id)" nfs'}), encoding="utf-8")
    code, row = cli("searched", "--run", str(run), "--fields", str(fields), "--results", "3")
    assert (code, row["query"]) == (0, 'wal "$(id)" nfs')
    code, row = cli("searched", "--run", str(run))
    assert code == 2
    assert "give the query" in row["error"]


def test_link_adds_the_kth_url_a_capture_lists(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    assert add(run, "--url", "https://a.example/p", "--file", capture(tmp_path, LINKS))[0] == 0
    code, leads = cli("links", "--run", str(run))
    assert code == 0
    assert {lead["url"]: lead["from"] for lead in leads} == {
        "https://e.example/x?a=1;touch${IFS}Z": ["S1:1"],
        "https://e.example/`id`": ["S1:2"],
    }
    code, row = add(run, "--link", "S1:2", "--unretrieved", "not read")
    assert (code, row["url"], row["id"]) == (0, "https://e.example/`id`", "S2")
    code, row = add(run, "--link", "S1:1", "--unretrieved", "not read")
    assert (code, row["url"]) == (0, "https://e.example/x?a=1;touch${IFS}Z")
    assert [lead["url"] for lead in cli("links", "--run", str(run))[1]] == []


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (["--link", "S1:9"], "S1's capture lists 2 links"),
        (["--link", "S7:1"], "no source S7"),
        (["--link", "one"], "expected S<n>:<k>"),
        (["--link", "S1:1", "--url", "https://a.example/z"], "--url or --link, not both"),
    ],
)
def test_link_refusals_name_the_reason(
    root: Path, tmp_path: Path, argv: list[str], reason: str
) -> None:
    run = new_run(root)
    assert add(run, "--url", "https://a.example/p", "--file", capture(tmp_path, LINKS))[0] == 0
    code, row = add(run, *argv, "--unretrieved", "x")
    assert code == 2
    assert reason in row["error"]


def test_a_damaged_ledger_row_stops_the_run(root: Path) -> None:
    run = new_run(root)
    assert add(run, "--url", "https://a.example/x", "--unretrieved", "paywall")[0] == 0
    ledger = run / topic.MANIFEST
    damaged = ledger.read_text(encoding="utf-8").replace('"quotes"', '"quotes')
    _ = ledger.write_text(damaged, encoding="utf-8")
    code, row = add(run, "--url", "https://a.example/y", "--unretrieved", "paywall")
    assert code == 2
    assert "sources.jsonl line 1 is damaged" in row["error"]
    assert ledger.read_text(encoding="utf-8") == damaged
    code, row = cli("verify", "--run", str(run), "--offline")
    assert (code, "line 1" in row["error"]) == (2, True)
    code, status = cli("status", "--root", str(root))
    assert code == 1
    assert "sources.jsonl line 1" in status["topics"][0]["error"]


def test_same_day_open_refuses_a_different_audience_or_mode(root: Path) -> None:
    _ = new_run(root, "t4")
    code, row = cli("open", "--root", str(root), "--topic", "t4", "--audience", "public")
    assert code == 2
    assert "mode research, audience private" in row["error"]
    assert "--audience" in row["error"]
    code, row = cli("open", "--root", str(root), "--topic", "t4", "--mode", "assessment")
    assert code == 2
    assert "--mode" in row["error"]
    assert cli("open", "--root", str(root), "--topic", "t4", "--audience", "private")[0] == 0


@pytest.mark.parametrize("command", ["status", "prior"])
def test_a_missing_root_is_an_error_not_an_empty_list(tmp_path: Path, command: str) -> None:
    missing = tmp_path / "no-such-root"
    code, row = cli(
        command, "--root", str(missing), *(["--topic", "t"] if command == "prior" else [])
    )
    assert code == 2
    assert str(missing) in row["error"]


def source(**fields: object) -> topic.Row:
    return {"id": "S1", "url": "https://a.example/x", **fields}


@pytest.mark.parametrize(
    ("row", "fetch", "state"),
    [
        (source(), stub(404), "vanished"),
        (source(), stub(410), "vanished"),
        (source(), stub(0), "unreachable"),
        (source(), stub(503), "unreachable"),
        (source(), stub(200, final="https://a.example/moved"), "moved"),
        (source(capture="fetch", sha256="0" * 64), stub(), "changed"),
        (source(capture="file", quotes=["not on the page"]), stub(), "misquoted"),
        (source(capture="file", quotes=["readers do not block writers"]), stub(), "ok"),
        (source(capture="fetch", sha256=topic.sha256(TXT.encode())), stub(), "ok"),
        (source(capture="file"), stub(), "reachable"),
        (source(), stub(), "reachable"),
    ],
)
def test_check_live_classifies_the_answer(row: topic.Row, fetch: topic.Fetch, state: str) -> None:
    assert topic.check_live(row, fetch)[0] == state


def test_a_live_answer_with_nothing_to_compare_is_not_verified(root: Path) -> None:
    run = new_run(root)
    assert add(run, "--url", "https://a.example/x", "--kind", "vendor")[0] == 0
    today = date.today().isoformat()  # noqa: DTZ011
    code, result = call(topic.cmd_verify, stub(), "verify", "--run", str(run))
    assert (code, result["counts"]) == (0, {"reachable": 1})
    assert topic.source_states(run, today) == {"S1": "reachable"}
    assert set(topic.source_states(run, today).values()) <= set(topic.SOURCE_STATES)


def test_a_captured_source_verifies_on_a_live_quote(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    q = "readers do not block writers"
    assert (
        add(run, "--url", "https://a.example/x", "--file", capture(tmp_path), "--quote", q)[0] == 0
    )
    assert call(topic.cmd_verify, stub(), "verify", "--run", str(run))[0] == 0
    assert topic.source_states(run, date.today().isoformat()) == {"S1": "verified"}  # noqa: DTZ011


def test_add_fetch_records_the_capture_and_what_the_server_said(root: Path) -> None:
    run = new_run(root)
    code, row = call(
        topic.cmd_add, stub(), "add", "--run", str(run), "--url", "https://a.example/x.txt",
        "--fetch", "--kind", "vendor", "--quote", "readers do not block",
    )  # fmt: skip
    assert code == 0, row
    assert row["capture"] == "fetch"
    assert row["sha256"] == topic.sha256(TXT.encode())
    assert row["response"] == {"status": 200, "content_type": "text/plain"}
    assert (run / "references" / row["file"]).read_bytes() == TXT.encode()
    assert not any("redirected" in w for w in row["warnings"])


def test_add_fetch_that_followed_a_redirect_records_the_final_url(root: Path) -> None:
    run = new_run(root)
    final = "https://a.example/final.txt"
    argv = (
        "add",
        "--run",
        str(run),
        "--url",
        "http://a.example/old.txt",
        "--fetch",
        "--kind",
        "vendor",
    )
    code, row = call(topic.cmd_add, stub(final=final), *argv)
    assert code == 0, row
    assert (row["url"], row["requested_url"]) == (final, "http://a.example/old.txt")
    assert any("redirected" in w and final in w for w in row["warnings"])
    code, result = call(topic.cmd_verify, stub(), "verify", "--run", str(run), "--id", "S1")
    assert (code, result["counts"]) == (0, {"ok": 1})
    code, again = call(topic.cmd_add, stub(final=final), *argv)
    assert (code, again["id"], again["duplicate"]) == (0, "S1", True)


def test_add_fetch_refuses_a_failed_download(root: Path) -> None:
    run = new_run(root)
    code, row = call(
        topic.cmd_add,
        stub(500),
        "add",
        "--run",
        str(run),
        "--url",
        "https://a.example/x",
        "--fetch",
    )
    assert code == 2
    assert "returned 500" in row["error"]
    assert not (run / topic.MANIFEST).exists()


def tomorrow() -> str:
    return (date.today() + timedelta(days=1)).isoformat()  # noqa: DTZ011


def test_a_later_day_carries_sources_framing_and_tables(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    q = "readers do not block writers"
    assert (
        add(run, "--url", "https://a.example/x", "--file", capture(tmp_path), "--quote", q)[0] == 0
    )
    assert add(run, "--url", "https://a.example/y", "--unretrieved", "paywall")[0] == 0
    assert cli("searched", "--run", str(run), "--query", "wal", "--results", "3")[0] == 0
    assert (
        cli("conflict", "--run", str(run), "--source", "S1", "--source", "S2", "--about", "x")[0]
        == 0
    )
    (run / "data").mkdir()
    _ = (run / "data" / "criteria.csv").write_text("criterion,rating\nA,strong\n", encoding="utf-8")
    _ = (run / "data" / "notes.log").write_text("not carried\n", encoding="utf-8")
    index = (
        (run / "index.md")
        .read_text(encoding="utf-8")
        .replace("- [ ] \n", "- [ ] Does WAL hold on NFS?\n")
    )
    _ = (run / "index.md").write_text(index, encoding="utf-8")

    code, opened = cli("open", "--root", str(root), "--topic", "wal", "--date", tomorrow())
    assert (code, opened["created"], opened["carried"]) == (0, True, 2)
    nxt = Path(opened["run_dir"])
    assert [p["date"] for p in opened["prior"]] == [run.parents[1].name]
    assert opened["meta"]["prior"] == run.parents[1].name
    rows = topic.read_jsonl(nxt / topic.MANIFEST)
    assert [r["id"] for r in rows] == ["S1", "S2"]
    assert all(r["carried_from"] == run.parents[1].name for r in rows)
    assert (nxt / "references" / str(rows[0]["file"])).read_bytes() == TXT.encode()
    assert all(r["carried_from"] for r in topic.read_jsonl(nxt / topic.SEARCHES))
    assert len(topic.read_jsonl(nxt / topic.CONFLICTS)) == 1
    assert (nxt / "data" / "criteria.csv").is_file()
    assert not (nxt / "data" / "notes.log").exists()
    text = (nxt / "index.md").read_text(encoding="utf-8")
    assert "Does WAL hold on NFS?" in text
    assert "carried 2 sources" in text
    assert topic.source_states(nxt, tomorrow()) == {"S1": "unverified", "S2": "unretrieved"}


def test_resume_logs_todays_visit_once_and_keeps_the_report(root: Path) -> None:
    run = earlier_day(root, "wal")
    _ = (run / "report.md").write_text("# T\n", encoding="utf-8")
    today = date.today().isoformat()  # noqa: DTZ011
    for _ in range(2):
        code, opened = cli(
            "open", "--root", str(root), "--topic", "wal", "--resume", "--date", tomorrow()
        )
        assert (code, opened["resumed"], opened["created"]) == (0, True, False)
    text = (run / "index.md").read_text(encoding="utf-8")
    assert text.count(f"- {today}: resumed") == 1
    assert f"- {tomorrow()}: resumed" not in text
    assert (run / "history" / f"report-{PAST}.md").is_file()


def test_run_reads_its_quote_from_a_file(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    fields = tmp_path / "q.json"
    _ = fields.write_text(json.dumps({"quote": "hello $(id)"}), encoding="utf-8")
    code, row = cli(
        "run", "--run", str(run), "--name", "b", "--fields", str(fields), "--",
        sys.executable, "-c", "print('hello $(id)')",
    )  # fmt: skip
    assert (code, row["quotes"]) == (0, ["hello $(id)"])
    _ = fields.write_text(json.dumps({"title": "x"}), encoding="utf-8")
    code, row = cli("run", "--run", str(run), "--name", "c", "--fields", str(fields), "--", "true")
    assert code == 2
    assert "'title' is not a field of run" in row["error"]


def test_a_carried_measured_source_is_not_verified_until_rerun(root: Path) -> None:
    run = new_run(root)
    code, row = cli(
        "run", "--run", str(run), "--name", "bench", "--quote", "hello", "--",
        sys.executable, "-c", "print('hello')",
    )  # fmt: skip
    assert code == 0, row
    assert (row["url"], row["kind"], row["exit"]) == ("measured:data/bench.log", "measured", 0)
    assert cli("verify", "--run", str(run))[0] == 0
    assert topic.source_states(run, tomorrow()) == {"S1": "verified"}

    nxt = Path(
        cli("open", "--root", str(root), "--topic", "wal", "--date", tomorrow())[1]["run_dir"]
    )
    assert topic.source_states(nxt, tomorrow()) == {"S1": "unverified"}
    assert cli("verify", "--run", str(nxt))[0] == 0
    assert topic.source_states(nxt, tomorrow()) == {"S1": "intact"}


def test_run_refuses_an_output_the_command_did_not_write(root: Path) -> None:
    run = new_run(root)
    out = run / "data" / "n.csv"
    argv = (
        "run",
        "--run",
        str(run),
        "--name",
        "b",
        "--output",
        str(out),
        "--",
        sys.executable,
        "-c",
    )
    code, row = cli(*argv, "pass")
    assert code == 2
    assert "did not write --output" in row["error"]
    code, row = cli(*argv, f"open({str(out)!r}, 'w').write('a,1')")
    assert (code, list(row["outputs"])) == (0, ["data/n.csv"])


def test_conflict_is_recorded_then_weighed(root: Path) -> None:
    run = new_run(root)
    for n in (1, 2):
        assert add(run, "--url", f"https://a.example/{n}", "--unretrieved", "x")[0] == 0
    sides = ("--source", "S1", "--source", "S2")
    code, row = cli("conflict", "--run", str(run), *sides, "--about", "latency")
    assert (code, row["id"], row["sources"]) == (0, "C1", ["S1", "S2"])
    code, row = cli("conflict", "--run", str(run), "--id", "C1", "--weight", "S1")
    assert code == 2
    assert "--why" in row["error"]
    code, row = cli(
        "conflict", "--run", str(run), "--id", "C1", "--weight", "S1", "--why", "measured"
    )
    assert (code, row["weight"], row["about"]) == (0, "S1", "latency")
    code, row = cli("conflict", "--run", str(run), "--id", "C9", "--weight", "S1")
    assert code == 2
    assert "no such conflict" in row["error"]
    code, row = cli(
        "conflict", "--run", str(run), "--source", "S1", "--source", "S7", "--about", "x"
    )
    assert code == 2
    assert "two or more current sources" in row["error"]


def test_status_lists_the_most_urgent_topic_first(root: Path, tmp_path: Path) -> None:
    broken = new_run(root, "broken")
    assert (
        add(
            broken,
            "--url",
            "https://a.example/x",
            "--file",
            capture(tmp_path),
            "--quote",
            "readers",
        )[0]
        == 0
    )
    next((broken / "references" / "raw").iterdir()).write_text("edited\n", encoding="utf-8")
    assert cli("verify", "--run", str(broken), "--offline")[0] == 1
    disputed = new_run(root, "disputed")
    for n in (1, 2):
        assert add(disputed, "--url", f"https://a.example/{n}", "--unretrieved", "x")[0] == 0
    sides = ("--source", "S1", "--source", "S2", "--about", "latency")
    assert cli("conflict", "--run", str(disputed), *sides)[0] == 0
    bare = new_run(root, "bare")
    topic.append_log(bare, "2099-01-01: reviewed")

    code, status = cli("status", "--root", str(root))
    assert code == 0
    ranked = [(r["topic"], r["urgency"], r["next_action"]) for r in status["topics"]]
    assert ranked == [("broken", 2, "verify"), ("disputed", 3, "continue"), ("bare", 7, "report")]
    assert status["recent"] == "research/bare"
    assert status["topics"][0]["sources"] == {"changed": 1}
    assert status["topics"][2]["updated"] == "2099-01-01"


def test_assessment_tally_and_one_grade_sensitivity(root: Path) -> None:
    run = new_run(root, "pick", "--mode", "assessment")
    table = (
        "criterion,uv,pip,sources\n"
        "Lock,strong,adequate,S1\nMigrate,weak,weak,S2\nCost,adequate,adequate,\n"
    )
    (run / "data").mkdir(exist_ok=True)
    _ = (run / "data" / "criteria.csv").write_text(table, encoding="utf-8")
    code, out = cli("tally", "--run", str(run))
    assert code == 0
    assert out["criteria"] == 3
    assert out["tally"]["uv"] == {"strong": 1, "adequate": 1, "weak": 1, "unknown": 0}
    assert out["tally"]["pip"] == {"strong": 0, "adequate": 2, "weak": 1, "unknown": 0}
    assert out["leader"] == "uv"
    assert out["sensitivity"]["survives"] is False
    assert out["sensitivity"]["flips"][0] == {
        "criterion": "Lock", "option": "uv", "from": "strong", "to": "adequate", "then": "tie",
    }  # fmt: skip


def test_a_note_admitting_no_evidence_contradicts_a_rating() -> None:
    by_id: dict[str, topic.Row] = {"S1": {"id": "S1", "kind": "independent"}}
    text = "criterion,rating,confidence,sources,note\nOS,strong,medium,S1,No evidence found\n"
    assert [f["rule"] for f in topic.lint_criteria(text, by_id)] == ["note-contradicts-rating"]
    assert "no evidence" in topic.MISSING_EVIDENCE_PHRASES


def test_ticked_counts_the_carried_questions_this_run_settled(root: Path) -> None:
    run = new_run(root)
    index = (run / "index.md").read_text(encoding="utf-8")
    _ = (run / "index.md").write_text(
        index.replace("- [ ] \n", "- [ ] Does WAL hold on NFS?\n- [ ] Is it safe on SMB?\n"),
        encoding="utf-8",
    )
    nxt = Path(
        cli("open", "--root", str(root), "--topic", "wal", "--date", tomorrow())[1]["run_dir"]
    )
    assert topic.ticked_since_prior(nxt) == 0
    text = (nxt / "index.md").read_text(encoding="utf-8")
    _ = (nxt / "index.md").write_text(
        text.replace("- [ ] Does WAL", "- [x] Does WAL"), encoding="utf-8"
    )
    assert topic.ticked_since_prior(nxt) == 1
    counts = topic.report_counts(nxt, "# T\n", {})
    assert (counts["ticked"], counts["open_questions"]) == (1, 1)


def criteria_run(root: Path) -> Path:
    run = new_run(root, "pick", "--mode", "assessment")
    assert (
        add(run, "--url", "https://a.example/1", "--kind", "independent", "--unretrieved", "x")[0]
        == 0
    )
    (run / "data").mkdir(exist_ok=True)
    table = (
        "criterion,uv,pip,confidence,sources,note\n"
        "Lock,strong,adequate,high,S1;S9,\n"
        "Cost,weak,,,,\n"
    )
    _ = (run / "data" / "criteria.csv").write_text(table, encoding="utf-8")
    return run


def test_tally_markdown_writes_the_criteria_section_from_the_csv(root: Path) -> None:
    code, text = cli("tally", "--run", str(criteria_run(root)), "--markdown")
    assert code == 0
    assert text.splitlines() == [
        "## Criteria",
        "",
        "- Lock: uv strong, pip adequate; high confidence; S1 (independent), S9 (not in the manifest).",  # noqa: E501
        "- Cost: uv weak, pip unknown; confidence not stated; no source.",
    ]


@pytest.mark.parametrize(
    ("text", "step", "topic_", "rest", "flags"),
    [
        (
            "continue sqlite-wal --fill --root=/r",
            "continue",
            "sqlite-wal",
            "sqlite-wal",
            {"fill": True, "root": "/r"},
        ),
        (
            "continue 'sqlite wal' --expand 'network drives'",
            "continue",
            "sqlite wal",
            "sqlite wal",
            {"expand": "network drives"},
        ),
        (
            "assess uv or pip --audience internal",
            "assess",
            None,
            "uv or pip",
            {"audience": "internal"},
        ),
        (
            "release wal --to 'the platform team' --offline",
            "release",
            "wal",
            "wal",
            {"to": "the platform team", "offline": True},
        ),
        ("status --namespace business", "status", None, "", {"namespace": "business"}),
        ("verify", "verify", None, "", {}),
        (
            "how does WAL work --mode research",
            None,
            None,
            "how does WAL work",
            {"mode": "research"},
        ),
        ("sqlite-wal --fill.", "continue", "sqlite-wal", "sqlite-wal", {"fill": True}),
        (
            "report wal. Use --root out and --date 2026-01-15. There is no network.",
            "report",
            None,
            "wal. Use and There is no network.",
            {"root": "out", "date": "2026-01-15"},
        ),
        (
            "verify vendor-y, --root out, --offline.",
            "verify",
            "vendor-y",
            "vendor-y,",
            {"root": "out", "offline": True},
        ),
        ("why don't readers block --root r", None, None, "why don't readers block", {"root": "r"}),
    ],
)
def test_route_parses_the_step_topic_and_flags(
    text: str, step: str | None, topic_: str | None, rest: str, flags: dict[str, t.Any]
) -> None:
    out = topic.route_arguments(text)
    assert (out["step"], out["topic"], out["request"], out["flags"]) == (
        step, topic_, rest, flags,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("wal --bogus", "unknown option --bogus"),
        ("wal --mode fast", "use one of research, assessment"),
        ("wal --date soon.", "expected YYYY-MM-DD"),
        ("continue wal --fill --expand x", "alternatives"),
        ("wal --resume=yes", "takes no value"),
        ("wal --root", "needs a value"),
    ],
)
def test_route_refuses_unknown_options_and_bad_values(text: str, reason: str) -> None:
    code, row = cli("route", "--", *text.split(" "))
    assert code == 2
    assert reason in row["error"]


@pytest.mark.parametrize(
    ("text", "flags"),
    [
        ("status --root .", {"root": "."}),
        ("status --root ../.. --namespace x", {"root": "../..", "namespace": "x"}),
        ('report wal --root="/srv/a b".', {"root": "/srv/a b"}),
    ],
)
def test_route_keeps_dot_paths_and_quoted_values(text: str, flags: dict[str, str]) -> None:
    assert topic.route_arguments(text)["flags"] == flags


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("wal --to 'the platform", "unterminated quote"),
        ("wal --root=", "needs a value"),
        ("wal --root ''", "needs a value"),
        ("wal --root a --root b", "given twice"),
    ],
)
def test_route_refuses_unclosed_empty_or_repeated_values(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        topic.route_arguments(text)


def test_route_reads_arguments_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("continue 'sqlite wal' --fill\n"))
    code, out = cli("route", "--stdin")
    assert (code, out["step"], out["topic"], out["references"]) == (
        0, "continue", "sqlite wal", ["continue.md"],
    )  # fmt: skip


def test_default_root_follows_the_windows_documents_folder_on_wsl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "scratch"))
    users = tmp_path / "Users"
    for name in ("alice", "bob", "Public"):
        (users / name / "Documents").mkdir(parents=True)
    wsl = tmp_path / "version"
    _ = wsl.write_text("Linux version 6.6 (Microsoft)", encoding="utf-8")
    plain = tmp_path / "plain"
    _ = plain.write_text("Linux version 6.6", encoding="utf-8")
    home = tmp_path / "home"
    here = {"proc_version": wsl, "windows_users_dir": users, "home": home}
    path = {"PATH": "/usr/bin:/mnt/c/Users/bob/AppData/Local/bin"}
    assert topic.resolve_root("/x", env={}, **here) == Path("/x")
    assert topic.resolve_root(None, env={"RESEARCH_ROOT": "/y"}, **here) == Path("/y")
    assert topic.resolve_root(None, env=path, **here) == users / "bob" / "Documents"
    monkeypatch.setattr(getpass, "getuser", lambda: "alice")
    assert topic.resolve_root(None, env={}, **here) == users / "alice" / "Documents"
    monkeypatch.setattr(getpass, "getuser", lambda: "nobody")
    with pytest.raises(ValueError, match="2 Windows Documents folders"):
        topic.resolve_root(None, env={}, **here)
    off = {**here, "proc_version": plain}
    assert topic.resolve_root(None, env={}, **off) == home / "Documents"


def test_default_root_is_never_the_temp_directory(tmp_path: Path) -> None:
    missing = tmp_path / "no-version"
    with pytest.raises(ValueError, match="temp directory"):
        topic.resolve_root(None, env={}, proc_version=missing, home=tmp_path)


def test_find_shows_where_text_occurs_in_the_captures(root: Path, tmp_path: Path) -> None:
    run = new_run(root)
    page = "<p>Readers  do not <b>block</b> writers in WAL mode.</p> <html></html>"
    assert (
        add(
            run, "--url", "https://a.example/x", "--file", capture(tmp_path, page), "--title", "WAL"
        )[0]
        == 0
    )
    assert add(run, "--url", "https://a.example/y", "--unretrieved", "paywall")[0] == 0
    code, hits = cli("find", "--run", str(run), "do NOT block", "--width", "6")
    assert code == 0
    assert [(h["id"], h["title"]) for h in hits] == [("S1", "WAL")]
    assert hits[0]["snippets"] == ["…aders do not block write…"]
    assert cli("find", "--run", str(run), "absent text")[1] == []


def chart(tmp_path: Path, csv_text: str, *argv: str) -> tuple[int, t.Any]:
    src = tmp_path / "data.csv"
    _ = src.write_text(csv_text, encoding="utf-8")
    return cli("chart", "--csv", str(src), "--out", str(tmp_path / "out" / "c.svg"), *argv)


def test_chart_draws_rating_bars_grouped_bars_and_lines(tmp_path: Path) -> None:
    code, row = chart(
        tmp_path, "criterion,rating\nSpeed,strong\nCost,weak\n", "--title", "Speed wins"
    )
    assert (code, row["rows"], row["kind"]) == (0, 2, "bar")
    svg = (tmp_path / "out" / "c.svg").read_text(encoding="utf-8")
    assert svg.count("<rect") == 2
    assert "Speed wins" in svg
    assert ">strong<" in svg
    code, _ = chart(
        tmp_path,
        "criterion,uv,pip\nA,strong,weak\nB,adequate,strong\n",
        "--value",
        "uv",
        "--value",
        "pip",
    )
    assert code == 0
    assert (tmp_path / "out" / "c.svg").read_text(encoding="utf-8").count("<rect") == 6
    code, row = chart(tmp_path, "month,ms\nJan,26\nFeb,14\n", "--kind", "line")
    assert (code, row["kind"]) == (0, "line")
    assert "<polyline" in (tmp_path / "out" / "c.svg").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("csv_text", "argv", "reason"),
    [
        ("a,b\n", (), "has no rows"),
        ("a,b\nx,1\n", ("--value", "zzz"), "has no column 'zzz'"),
        ("a\nx\n", (), "needs a label column"),
    ],
)
def test_chart_refuses_a_table_it_cannot_draw(
    tmp_path: Path, csv_text: str, argv: tuple[str, ...], reason: str
) -> None:
    code, row = chart(tmp_path, csv_text, *argv)
    assert code == 2
    assert reason in row["error"]


def test_assessment_lint_asks_for_sensitivity_flip_and_rated_sources(root: Path) -> None:
    run = criteria_run(root)
    rows = topic.current(topic.read_jsonl(run / topic.MANIFEST))
    found = topic.lint_assessment("The verdict is uv.", run, rows)
    assert [f["rule"] for f in found][:2] == ["no-sensitivity", "no-flip"]
    assert "unsourced-rating" in {f["rule"] for f in found}
    text = "Sensitivity: the verdict survives one rating moving. Evidence that would flip it: x."
    assert {f["rule"] for f in topic.lint_assessment(text, run, rows)} == {
        "sample-of-one-high",
        "unsourced-rating",
    }
