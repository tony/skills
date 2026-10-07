"""Tests for sweep.py."""

# ruff: noqa: S101, S603, S607, INP001
from __future__ import annotations

import json
import subprocess
import typing as t

import sweep  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    import pathlib

    import pytest


def _finding(**over: str) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "f1",
        "verdict": "absent",
        "skill": "demo:used",
        "expected_change": "pastes drop below 2 per 30 days",
    }
    return {**base, **over}


def test_counts_without_boundary_ranks_all_time(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Omitting --boundary yields an all-time ranking and no era fields."""
    history = tmp_path / "history.jsonl"
    rec = {"display": "/demo:used go", "timestamp": 1790000000000, "project": "/p"}
    _ = history.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    code = sweep.main(["counts", "--history", str(history), "--tool-unavailable"])
    assert code == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    assert out["rank_all"] == ["demo:used"]
    assert out["rank_era"] == []
    assert "slash_era" not in out["skills"]["demo:used"]


def _repo(path: pathlib.Path) -> None:
    for cmd in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.invalid"],
        ["config", "user.name", "t"],
        ["commit", "-q", "--allow-empty", "-m", "init"],
    ):
        _ = subprocess.run(["git", *cmd], cwd=path, check=True)


def test_ledger_round_trip_rejects_edited_skill(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ledger-save then ledger-verify passes; changing skill afterwards fails."""
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    findings = tmp_path / "findings.json"
    _ = findings.write_text(json.dumps([_finding()]), encoding="utf-8")
    ledger = tmp_path / "out" / "ledger.json"
    argv = ["ledger-save", "--findings", str(findings), "--out", str(ledger)]
    code = sweep.main(argv)
    assert code == 0
    _ = capsys.readouterr()
    code = sweep.main(["ledger-verify", str(ledger)])
    assert code == 0

    data = t.cast("dict[str, t.Any]", json.loads(ledger.read_text(encoding="utf-8")))
    data["findings"][0]["skill"] = "demo:other"
    _ = ledger.write_text(json.dumps(data), encoding="utf-8")
    _ = capsys.readouterr()
    code = sweep.main(["ledger-verify", str(ledger)])
    assert code == 1
    assert "findings changed" in capsys.readouterr().out


def test_ledger_key_ignores_evidence_fields() -> None:
    """Evidence edits keep the key; every acted-on field changes it."""
    base = sweep.ledger_key("h", [_finding()])
    assert base == sweep.ledger_key("h", [{**_finding(), "ratio": "9 of 10"}])
    for field in ("verdict", "skill", "expected_change"):
        assert base != sweep.ledger_key("h", [_finding(**{field: "changed"})])
