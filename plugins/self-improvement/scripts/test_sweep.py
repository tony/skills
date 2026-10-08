"""Tests for sweep.py."""

# ruff: noqa: S101, S603, S607, INP001
from __future__ import annotations

import json
import subprocess
import typing as t
from pathlib import Path

import pytest
import sweep  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    import pathlib


HALF = 6
AUTOSQUASH_ABORTED = 2


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


def _git(path: pathlib.Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _skill(path: pathlib.Path, name: str, extra: str = "") -> None:
    skill = path / "plugins" / "demo" / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True)
    _ = skill.write_text(f"---\nname: {name}\n{extra}---\nbody\n", encoding="utf-8")


def test_catalog_lists_skills_with_gating_and_birth(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catalog reports each tracked skill, its gating, and its first commit date."""
    _repo(tmp_path)
    _skill(tmp_path, "open")
    _skill(tmp_path, "gated", "disable-model-invocation: true\n")
    _ = _git(tmp_path, "add", "plugins")
    _ = _git(tmp_path, "commit", "-q", "-m", "Add skills")
    code = sweep.main(["catalog", "--root", str(tmp_path)])
    assert code == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    skills = t.cast("list[dict[str, t.Any]]", out["skills"])
    by_name = {t.cast("str", s["name"]): s for s in skills}
    assert set(by_name) == {"demo:open", "demo:gated"}
    assert by_name["demo:gated"]["gated"] is True
    assert by_name["demo:open"]["gated"] is False
    assert by_name["demo:open"]["born"]
    assert out["era"]["date"] == ""


def test_tree_check_commitless_repo_falls_back(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """tree-check on a repo with no commits reports staged files instead of crashing."""
    _ = subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    assert sweep.main(["tree-check"]) == 0
    _ = capsys.readouterr()
    _ = (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    _ = _git(tmp_path, "add", "notes.txt")
    assert sweep.main(["tree-check"]) == 1
    assert json.loads(capsys.readouterr().out)["dirty"] == ["notes.txt"]


def test_tree_check_flags_modified_and_untracked_catalog_files(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """tree-check flags a modified tracked file and an untracked file under plugins/."""
    _repo(tmp_path)
    _skill(tmp_path, "open")
    _ = _git(tmp_path, "add", "plugins")
    _ = _git(tmp_path, "commit", "-q", "-m", "Add skill")
    monkeypatch.chdir(tmp_path)
    assert sweep.main(["tree-check"]) == 0
    _ = capsys.readouterr()
    skill = tmp_path.joinpath("plugins", "demo", "skills", "open", "SKILL.md")
    _ = skill.write_text("changed\n", encoding="utf-8")
    _ = tmp_path.joinpath("plugins", "demo", "new.md").write_text("x", encoding="utf-8")
    _ = (tmp_path / ".zshrc").write_text("x", encoding="utf-8")
    assert sweep.main(["tree-check"]) == 1
    dirty = t.cast("list[str]", json.loads(capsys.readouterr().out)["dirty"])
    assert dirty == [
        Path("plugins", "demo", "new.md").as_posix(),
        Path("plugins", "demo", "skills", "open", "SKILL.md").as_posix(),
    ]


def test_autosquash_folds_fixup_commits(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Autosquash leaves no fixup! commit and keeps the fix in the target commit."""
    _repo(tmp_path)
    for name in ("a", "b"):
        _ = (tmp_path / f"{name}.txt").write_text(name, encoding="utf-8")
        _ = _git(tmp_path, "add", f"{name}.txt")
        _ = _git(tmp_path, "commit", "-q", "-m", f"Add {name}")
    target = _git(tmp_path, "log", "--format=%H", "--grep=Add a")
    _ = (tmp_path / "a.txt").write_text("a fixed", encoding="utf-8")
    _ = _git(tmp_path, "commit", "-q", "-a", f"--fixup={target}")
    monkeypatch.chdir(tmp_path)
    assert sweep.main(["autosquash", "--onto", target]) == 0
    assert json.loads(capsys.readouterr().out) == {"squashed": True, "unsquashed": []}
    assert _git(tmp_path, "log", "--format=%s", f"{target}^..HEAD") == "Add b\nAdd a"
    assert _git(tmp_path, "show", "HEAD:a.txt") == "a fixed"


def test_autosquash_conflict_aborts_and_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fixup that conflicts with a later commit aborts the rebase and exits 2."""
    _repo(tmp_path)
    target_file = tmp_path / "a.txt"
    _ = target_file.write_text("one\n", encoding="utf-8")
    _ = _git(tmp_path, "add", "a.txt")
    _ = _git(tmp_path, "commit", "-q", "-m", "Add a")
    target = _git(tmp_path, "rev-parse", "HEAD")
    _ = target_file.write_text("two\n", encoding="utf-8")
    _ = _git(tmp_path, "commit", "-q", "-a", "-m", "Edit a")
    _ = target_file.write_text("three\n", encoding="utf-8")
    _ = _git(tmp_path, "commit", "-q", "-a", f"--fixup={target}")
    before = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    assert sweep.main(["autosquash", "--onto", target]) == AUTOSQUASH_ABORTED
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"squashed": False, "aborted": True}
    assert "rebase aborted" in captured.err
    assert _git(tmp_path, "rev-parse", "HEAD") == before
    assert _git(tmp_path, "status", "--porcelain") == ""
    assert not Path(_git(tmp_path, "rev-parse", "--git-path", "rebase-merge")).exists()


def test_counts_window_numerator_and_denominator(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--window reports matches, the windowed denominator, and spread per skill."""
    history = tmp_path / "history.jsonl"
    day = 86400000
    start = 1790000000000
    lines: list[dict[str, object]] = []
    for i in range(12):
        tail = " no trailer" if i < HALF else ""
        lines.append(
            {
                "display": f"/demo:used run {i}{tail}",
                "timestamp": start + i * day,
                "project": f"/p{i % 3}",
            }
        )
    lines.append(
        {"display": "/demo:used old no trailer", "timestamp": start - 400 * day, "project": "/z"}
    )
    lines.append({"display": "run lint then test", "timestamp": start, "project": "/p0"})
    lines.append({"display": "run lint then test", "timestamp": start, "project": "/p1"})
    _ = history.write_text("\n".join(json.dumps(r) for r in lines) + "\n", encoding="utf-8")
    since = "2026-01-01"
    code = sweep.main(
        [
            "counts",
            "--history",
            str(history),
            "--tool-unavailable",
            "--window",
            f"demo:used@{since}@no trailer",
            "--window",
            f"@{since}@run lint",
        ]
    )
    assert code == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    used, unnamed = t.cast("list[dict[str, t.Any]]", out["windows"])
    assert (used["invocations"], used["matched"], used["projects"], used["ratio"]) == (
        12,
        6,
        3,
        0.5,
    )
    assert (unnamed["matched"], unnamed["projects"]) == (2, 2)


def test_catalog_flags_shallow_clone_and_hides_births(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A shallow clone reports shallow and no birth dates instead of false ones."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _repo(origin)
    _skill(origin, "open")
    _ = _git(origin, "add", "plugins")
    _ = _git(origin, "commit", "-q", "-m", "Add skill")
    clone = tmp_path / "clone"
    _ = subprocess.run(["git", "clone", "-q", "--depth=1", origin.as_uri(), str(clone)], check=True)
    assert sweep.main(["catalog", "--root", str(clone)]) == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    assert out["shallow"] is True
    assert out["skills"][0]["born"] == ""
    assert out["era"]["date"] == ""


def test_catalog_glob_reads_a_flat_skills_directory(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--catalog-glob catalogs skills/<name>/ and .claude/skills/<name>/ with bare names."""
    _repo(tmp_path)
    for rel in ("skills/flat", ".claude/skills/local"):
        skill = tmp_path / rel / "SKILL.md"
        skill.parent.mkdir(parents=True)
        _ = skill.write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
    _ = _git(tmp_path, "add", "-Af")
    _ = _git(tmp_path, "commit", "-q", "-m", "Add skills")
    for glob, name in (("skills/*/SKILL.md", "flat"), (".claude/skills/*/SKILL.md", "local")):
        assert sweep.main(["catalog", "--root", str(tmp_path), "--catalog-glob", glob]) == 0
        out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
        assert [s["name"] for s in t.cast("list[dict[str, t.Any]]", out["skills"])] == [name]


def test_catalog_survives_a_moved_but_uncommitted_skill(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tracked skill missing from the working tree is read from HEAD, not a crash."""
    _repo(tmp_path)
    _skill(tmp_path, "a")
    _ = _git(tmp_path, "add", "plugins")
    _ = _git(tmp_path, "commit", "-q", "-m", "Add skill")
    (tmp_path / "plugins" / "demo" / "skills" / "a" / "SKILL.md").unlink()
    assert sweep.main(["catalog", "--root", str(tmp_path)]) == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    assert [s["name"] for s in t.cast("list[dict[str, t.Any]]", out["skills"])] == ["demo:a"]


def test_catalog_skips_a_file_absent_from_head_and_tree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An added-then-deleted skill has no text anywhere and is skipped."""
    _repo(tmp_path)
    _skill(tmp_path, "a")
    _ = _git(tmp_path, "add", "plugins")
    (tmp_path / "plugins" / "demo" / "skills" / "a" / "SKILL.md").unlink()
    assert sweep.main(["catalog", "--root", str(tmp_path)]) == 0
    out = t.cast("dict[str, t.Any]", json.loads(capsys.readouterr().out))
    assert out["skills"] == []


def test_validate_findings_rejects_unknown_verdict() -> None:
    """Only absent and not-binding are accepted verdicts."""
    with pytest.raises(ValueError, match="unknown verdict"):
        _ = sweep.validate_findings([_finding(verdict="maybe")])


def test_git_failure_shows_stderr(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside a repository the error carries git's own message."""
    assert sweep.main(["catalog", "--root", str(tmp_path)]) == AUTOSQUASH_ABORTED
    assert "not a git repository" in capsys.readouterr().err
