"""Tests for resources.py."""

# ruff: noqa: S101, S603, S607, INP001
from __future__ import annotations

import json
import subprocess
import sys
import typing as t

import pytest
import resources  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    import pathlib

GIB = 2**30
CHILD_EXIT = 3
PEAK_FLOOR_MIB = 90


def _fake_proc(root: pathlib.Path, *, pressure: bool = True) -> pathlib.Path:
    proc = root / "proc"
    proc.mkdir()
    meminfo = "MemTotal: 16384000 kB\nMemAvailable: 4194304 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n"
    _ = (proc / "meminfo").write_text(meminfo, encoding="utf-8")
    if pressure:
        (proc / "pressure").mkdir()
        cpu = "some avg10=12.50 avg60=1.00 avg300=0.50 total=1\n"
        memory = "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00\n"
        _ = (proc / "pressure" / "cpu").write_text(cpu, encoding="utf-8")
        _ = (proc / "pressure" / "memory").write_text(memory, encoding="utf-8")
    return proc


def test_snapshot_reads_fake_proc(tmp_path: pathlib.Path) -> None:
    """Memory and pressure come from /proc; free space from the filesystem itself."""
    snap = resources.snapshot([tmp_path], proc=_fake_proc(tmp_path))
    assert snap["mem_available_bytes"] == 4194304 * 1024
    assert snap["cpu_pressure_pct"] == pytest.approx(12.5)
    assert snap["mem_pressure_pct"] == pytest.approx(0.0)
    filesystems = t.cast("dict[str, dict[str, object]]", snap["filesystems"])
    assert set(filesystems[str(tmp_path)]) == {"free_bytes", "free_inodes"}


def test_snapshot_without_pressure_reports_none(tmp_path: pathlib.Path) -> None:
    """Kernels without pressure stall information report it as unknown."""
    snap = resources.snapshot([tmp_path], proc=_fake_proc(tmp_path, pressure=False))
    assert snap["cpu_pressure_pct"] is None


def _snap(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "filesystems": {"/": {"free_bytes": 212 * GIB, "free_inodes": 10**6}},
        "mem_available_bytes": int(9.8 * GIB),
        "cpu_pressure_pct": 3.0,
        "mem_pressure_pct": 0.0,
    }
    return {**base, **over}


def test_breaches_names_each_reserve() -> None:
    """Every reserve under its floor is named, filesystems first."""
    snap = _snap(
        filesystems={"/": {"free_bytes": 10 * GIB, "free_inodes": 500}},
        mem_available_bytes=2 * GIB,
        cpu_pressure_pct=70.0,
        mem_pressure_pct=1.0,
    )
    breached = resources.breaches(snap, resources.Reserves())
    assert breached == ["disk /", "inodes /", "memory", "cpu pressure"]


def test_breaches_skip_unreported_inodes_and_pressure() -> None:
    """A filesystem with no inode count and a kernel without pressure never breach."""
    snap = _snap(
        filesystems={"/mnt/c": {"free_bytes": 300 * GIB, "free_inodes": None}},
        cpu_pressure_pct=None,
        mem_pressure_pct=None,
    )
    assert resources.breaches(snap, resources.Reserves()) == []


def test_summary_line_ok() -> None:
    """The line the Claude evaluator reads, when nothing is low."""
    line = resources.summary_line(_snap(), [])
    assert line == "resources ok: 212 GiB free, 9.8 GiB available, cpu pressure 3%"


def test_summary_line_low_names_breaches() -> None:
    """A low line names each breach before the readings."""
    snap = _snap(mem_available_bytes=2 * GIB)
    line = resources.summary_line(snap, ["memory"])
    assert line == "resources low (memory): 212 GiB free, 2.0 GiB available, cpu pressure 3%"


def test_check_cli_exits_one_on_breach(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An impossible disk reserve breaches and prints a low line first."""
    args = ["check", "--path", str(tmp_path), "--reserve-disk-gib", "1000000000"]
    assert resources.main(args) == 1
    assert capsys.readouterr().out.startswith("resources low (disk ")


def test_sample_returns_command_exit_code() -> None:
    """Sampling a command passes its exit code through."""
    code = resources.main(["sample", "--", sys.executable, "-c", "raise SystemExit(3)"])
    assert code == CHILD_EXIT


def test_register_merges_roots(tmp_path: pathlib.Path) -> None:
    """Registering roots twice keeps one entry per root."""
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [tmp_path / "a"])
    resources.register(manifest, [tmp_path / "a", tmp_path / "b"])
    roots = t.cast("dict[str, list[str]]", json.loads(manifest.read_text(encoding="utf-8")))
    assert roots["roots"] == [str(tmp_path / "a"), str(tmp_path / "b")]


def _git(repo: pathlib.Path, *args: str) -> None:
    _ = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.mark.integration
def test_clean_removes_only_ignored_dirs_in_registered_roots(tmp_path: pathlib.Path) -> None:
    """Only an ignored, untracked, real directory inside a registered worktree goes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _ = (repo / ".gitignore").write_text("target/\n", encoding="utf-8")
    (repo / "target").mkdir()
    _ = (repo / "target" / "out.o").write_text("x", encoding="utf-8")
    (repo / "build").mkdir()
    _ = (repo / "build" / "keep.txt").write_text("tracked", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "node_modules").symlink_to(outside, target_is_directory=True)
    _git(repo, "add", ".gitignore", "build/keep.txt")
    _git(repo, "commit", "-q", "-m", "init")
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [repo])

    dry = resources.clean(manifest, apply=False)
    assert dry["would_remove"] == [str(repo / "target")]
    assert (repo / "target").exists()
    refused = " ".join(dry["refused"])
    assert "build" in refused
    assert "node_modules" in refused

    done = resources.clean(manifest, apply=True)
    assert done["removed"] == [str(repo / "target")]
    assert not (repo / "target").exists()
    assert (repo / "build" / "keep.txt").exists()
    assert outside.exists()


@pytest.mark.integration
def test_clean_refuses_a_root_that_is_not_a_worktree(tmp_path: pathlib.Path) -> None:
    """Without git to say what is ignored, nothing is removed."""
    root = tmp_path / "plain"
    (root / "target").mkdir(parents=True)
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [root])
    result = resources.clean(manifest, apply=True)
    assert result["removed"] == []
    assert (root / "target").exists()
    assert any("not a git worktree" in r for r in result["refused"])


def test_sample_reports_peak_rss_of_a_short_child(capsys: pytest.CaptureFixture[str]) -> None:
    """A child that exits between polls still reports its peak from getrusage."""
    script = "b = bytearray(96 * 2**20); b[::4096] = b'x' * len(b[::4096])"
    assert resources.main(["sample", "--interval", "5", "--", sys.executable, "-c", script]) == 0
    report = t.cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert t.cast("float", report["max_rss_mib"]) >= PEAK_FLOOR_MIB


def test_inodes_count_only_when_reported() -> None:
    """Zero free inodes is a real reading; a free count above the total is not."""
    assert resources.reported_inodes(1000, 0) == 0
    assert resources.reported_inodes(999, 1000000) is None
    assert resources.reported_inodes(0, 0) is None


@pytest.mark.integration
def test_clean_never_enters_nested_repositories(tmp_path: pathlib.Path) -> None:
    """A worktree or clone inside a registered root keeps its tracked build files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _ = (repo / ".gitignore").write_text(".worktrees/\nvendor/\n", encoding="utf-8")
    for nested in (repo / ".worktrees" / "feat", repo / "vendor" / "lib"):
        nested.mkdir(parents=True)
        _git(nested, "init", "-q")
        (nested / "build").mkdir()
        _ = (nested / "build" / "make.sh").write_text("echo", encoding="utf-8")
        (nested / ".venv").mkdir()
        _git(nested, "add", "build/make.sh")
        _git(nested, "commit", "-q", "-m", "init")
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [repo])
    result = resources.clean(manifest, apply=True)
    assert result["removed"] == []
    assert (repo / ".worktrees" / "feat" / "build" / "make.sh").exists()
    assert (repo / "vendor" / "lib" / ".venv").exists()
    assert any("nested repository" in r for r in result["refused"])


@pytest.mark.integration
def test_clean_attributes_candidates_by_path_not_prefix(tmp_path: pathlib.Path) -> None:
    """A root named like another root's prefix still owns its own artifacts."""
    repos = [tmp_path / "proj", tmp_path / "proj-2"]
    for repo in repos:
        repo.mkdir()
        _git(repo, "init", "-q")
        _ = (repo / ".gitignore").write_text("target/\n", encoding="utf-8")
        (repo / "target").mkdir()
    manifest = tmp_path / "owned.json"
    resources.register(manifest, repos)
    dry = resources.clean(manifest, apply=False)
    assert sorted(dry["would_remove"]) == sorted(str(r / "target") for r in repos)
    assert dry["refused"] == []
