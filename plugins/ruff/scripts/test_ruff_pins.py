"""Tests for ruff_pins.py."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest
import ruff_pins  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib


def test_sites_finds_each_pin_and_skips_vendored_trees(tmp_path: pathlib.Path) -> None:
    """Metadata, requirements, pre-commit rev and workflow lines are found; .venv is not."""
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\nlint = ["ruff>=0.9.0"]\n')
    (tmp_path / "requirements-ci.txt").write_text("ruff==0.9.1\nblack==1\n")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.9.2\n"
    )
    flow = tmp_path / ".github" / "workflows"
    flow.mkdir(parents=True)
    (flow / "ci.yml").write_text("      - run: pip install ruff==0.9.3\n")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyproject.toml").write_text('x = "ruff>=0.1.0"\n')
    found = {(p, n) for p, n, _ in ruff_pins.sites(str(tmp_path))}
    assert found == {
        ("pyproject.toml", 2),
        ("requirements-ci.txt", 1),
        (".pre-commit-config.yaml", 3),
        (".github/workflows/ci.yml", 1),
    }


def test_locked_reads_lockfile_and_compares(tmp_path: pathlib.Path) -> None:
    """The uv.lock entry is the resolved version; compare says how it sits against the target."""
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "ruff"\nversion = "0.9.1"\nsource = {}\n'
    )
    assert ruff_pins.locked(str(tmp_path)) == [("uv.lock", "0.9.1")]
    assert ruff_pins.compare("0.9.1", "0.16.10") == "behind"
    assert ruff_pins.compare("0.16.10", "0.9.1") == "ahead"


def test_non_numeric_version_exits_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-release spelling is refused rather than compared wrongly."""
    (tmp_path / "requirements.txt").write_text("ruff==0.9.1rc1\n")
    assert ruff_pins.main(["locked", str(tmp_path), "--target", "0.9.2"]) == 2
    assert "not a dotted numeric version" in capsys.readouterr().err


def test_lapse_uses_latest_matching_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The lapse is the latest upload among the platform's files plus the cooldown."""
    index = {
        "releases": {
            "1.0.0": [
                {
                    "filename": "r-1.0.0-linux.whl",
                    "upload_time_iso_8601": "2026-01-01T00:00:00.500000Z",
                },
                {"filename": "r-1.0.0-mac.whl", "upload_time_iso_8601": "2026-01-03T12:00:00Z"},
            ]
        }
    }
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    assert (
        ruff_pins.main(["lapse", "--version", "1.0.0", "--cooldown", "7d", "--json", str(path)])
        == 0
    )
    assert "lapses\t2026-01-10T12:00:00+00:00" in capsys.readouterr().out
    args = ["lapse", "--version", "1.0.0", "--cooldown", "7d", "--json", str(path)]
    assert ruff_pins.main([*args, "--filename-contains", "linux"]) == 0
    assert "lapses\t2026-01-08T00:00:00.500000+00:00" in capsys.readouterr().out


def test_lapse_missing_release_exits_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown release gives no time, never a guess."""
    path = tmp_path / "index.json"
    path.write_text('{"releases": {}}')
    assert (
        ruff_pins.main(["lapse", "--version", "9.9.9", "--cooldown", "7d", "--json", str(path)])
        == 2
    )
    assert "no release 9.9.9" in capsys.readouterr().err


def test_locked_reports_valid_entries_beside_a_prerelease(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One non-numeric entry is its own error row; the valid entries still print."""
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "ruff"\nversion = "0.9.1"\n')
    (tmp_path / "poetry.lock").write_text('[[package]]\nname = "ruff"\nversion = "0.13.0rc1"\n')
    assert ruff_pins.main(["locked", str(tmp_path), "--target", "0.9.2"]) == 2
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["poetry.lock\t0.13.0rc1\terror", "uv.lock\t0.9.1\tbehind"]
    assert "not a dotted numeric version" in captured.err


@pytest.mark.integration
def test_scope_walks_roots_and_matches_owner(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Repositories under --root are listed with owner, ruff config, pins and branch state."""
    for name, owner in (("a", "mine"), ("b", "theirs")):
        repo = tmp_path / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        remote = f"git@github.com:{owner}/{name}.git"
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    (tmp_path / "a" / "ruff.toml").write_text("[lint]\n")
    (tmp_path / "a" / "requirements.txt").write_text("ruff==0.9.1\n")
    mine = str(tmp_path / "a")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(
        ["git", "-C", mine, *ident, "commit", "-q", "--allow-empty", "-m", "x"], check=True
    )
    subprocess.run(["git", "-C", mine, "branch", "bump"], check=True)
    args = ["scope", "--root", str(tmp_path), "--owner", "mine", "--branch", "bump"]
    assert ruff_pins.main([*args, "--repo", "nobody/none"]) == 2
    rows = [line.split("\t") for line in capsys.readouterr().out.splitlines()]
    by = {r[1]: r for r in rows}
    assert by["mine/a"][5] == "exists"
    assert by["theirs/b"][5] == "none"
    assert by["theirs/b"][6] == "none"
    assert by["mine/a"][2:5] == ["yes", "ruff.toml", "1"]
    assert by["theirs/b"][2:5] == ["no", "none", "0"]
    assert by["unresolved"][0] == "nobody/none"


@pytest.mark.integration
def test_scope_finds_nested_config_and_worktree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A nested-only ruff config is reported by path, and a worktree on the branch shows."""
    repo = tmp_path / "mono"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "pyproject.toml").write_text("[tool.ruff]\nline-length = 99\n")
    (repo / "svc").mkdir()
    (repo / "svc" / ".ruff.toml").write_text("[lint]\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), *ident, "commit", "-q", "-m", "x"], check=True)
    wt = tmp_path / "elsewhere"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", "bump", str(wt)], check=True
    )
    assert ruff_pins.main(["scope", "--repo", str(repo), "--branch", "bump"]) == 0
    row = capsys.readouterr().out.splitlines()[0].split("\t")
    assert row[3] == "pkg/pyproject.toml,svc/.ruff.toml"
    assert row[6] == "exists"


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--repo", "a;rm -rf x"),
        ("--repo", "../nowhere"),
        ("--owner", "$(id)"),
        ("--branch", "a..b"),
    ],
)
def test_scope_refuses_unsafe_values(
    flag: str, value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Values the model extracts from user text are vetted by form before any git call."""
    assert ruff_pins.main(["scope", flag, value]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert flag in err


@pytest.mark.integration
def test_scope_accepts_directory_paths(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An existing directory is a path, whatever it contains: relative, '..', spaces."""
    for name in ("sibling", "my repo"):
        subprocess.run(["git", "init", "-q", str(tmp_path / name)], check=True)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    args = ["scope", "--repo", "../sibling", str(tmp_path / "my repo")]
    assert ruff_pins.main(args) == 0
    rows = [line.split("\t")[0] for line in capsys.readouterr().out.splitlines()]
    assert rows == [str(tmp_path / "sibling"), str(tmp_path / "my repo")]
