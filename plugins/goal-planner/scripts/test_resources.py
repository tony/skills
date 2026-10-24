"""Tests for resources.py."""

# ruff: noqa: S101, S603, S607, INP001
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import typing as t
from pathlib import Path

import pytest
import resources  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    import pathlib

GIB = 2**30
CHILD_EXIT = 3
PEAK_FLOOR_MIB = 90
TINY_MIB = 8


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


def test_snapshot_reads_unreadable_pressure_as_unknown(tmp_path: pathlib.Path) -> None:
    """A pressure file the kernel refuses to read, as with PSI disabled, is unknown."""
    proc = _fake_proc(tmp_path)
    (proc / "pressure" / "cpu").chmod(0)
    try:
        snap = resources.snapshot([tmp_path], proc=proc)
    finally:
        (proc / "pressure" / "cpu").chmod(0o644)
    assert snap["cpu_pressure_pct"] is None


class _DiskUsage(t.NamedTuple):
    total: int
    used: int
    free: int


def _windows_disk_usage(_path: object) -> _DiskUsage:
    return _DiskUsage(9 * GIB, 4 * GIB, 5 * GIB)


def test_snapshot_without_statvfs_or_loadavg(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without POSIX statvfs and load averages, as on Windows, free space still reads."""
    monkeypatch.delattr(os, "statvfs")
    monkeypatch.delattr(os, "getloadavg")
    monkeypatch.setattr(shutil, "disk_usage", _windows_disk_usage)
    snap = resources.snapshot([tmp_path], proc=_fake_proc(tmp_path))
    assert snap["filesystems"] == {str(tmp_path): {"free_bytes": 5 * GIB, "free_inodes": None}}
    assert snap["load"] is None


NO_RESOURCE_MODULE = (
    "import runpy, sys; sys.modules['resource'] = None; sys.argv = sys.argv[1:]; "
    "runpy.run_path(sys.argv[0], run_name='__main__')"
)


def test_scripts_run_without_the_resource_module(tmp_path: pathlib.Path) -> None:
    """Without the POSIX resource module, check still runs and sample reports no CPU time."""
    base = [sys.executable, "-c", NO_RESOURCE_MODULE, str(Path(resources.__file__))]
    check = subprocess.run(
        [*base, "check", "--path", str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert check.stdout.startswith("resources ")
    sampled = subprocess.run(
        [*base, "sample", "--", sys.executable, "-c", "pass"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(sampled.stdout.splitlines()[-1])["user_seconds"] is None


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


def _registered(
    manifest: pathlib.Path, capsys: pytest.CaptureFixture[str], *roots: pathlib.Path
) -> list[str]:
    """Register roots through the CLI and return every root the manifest holds."""
    assert resources.main(["register", "--manifest", str(manifest), *map(str, roots)]) == 0
    return t.cast("list[str]", json.loads(capsys.readouterr().out)["roots"])


def test_register_merges_roots(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Registering roots twice keeps one entry per root."""
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [tmp_path / "a"])
    roots = _registered(manifest, capsys, tmp_path / "a", tmp_path / "b")
    assert roots == [str(tmp_path / "a"), str(tmp_path / "b")]


def test_register_keeps_a_root_another_goal_added_meanwhile(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A goal that read the manifest before another registered keeps the other's root."""
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [tmp_path / "a"])
    stale = [str(tmp_path / "a")]
    resources.register(manifest, [tmp_path / "b"])

    def read_before_b(_manifest: pathlib.Path) -> list[str]:
        return stale

    with monkeypatch.context() as patch:
        patch.setattr(resources, "_roots", read_before_b)
        resources.register(manifest, [tmp_path / "c"])
    assert _registered(manifest, capsys, tmp_path / "a") == [str(tmp_path / n) for n in "abc"]


def test_register_survives_a_manifest_cut_short(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A crash mid-write loses the entry it was writing, not the manifest."""
    manifest = tmp_path / "owned.json"
    resources.register(manifest, [tmp_path / "a"])
    with manifest.open("a", encoding="utf-8") as handle:
        _ = handle.write(f'"{tmp_path / "half"}')
    roots = _registered(manifest, capsys, tmp_path / "b")
    assert roots == [str(tmp_path / "a"), str(tmp_path / "b")]


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


def _sample_peak_mib(*command: str) -> float | None:
    """Sample a command from a fresh interpreter, whose own footprint is small."""
    script = str(Path(resources.__file__))
    out = subprocess.run(
        [sys.executable, script, "sample", "--interval", "5", "--", *command],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return t.cast("float | None", json.loads(out)["max_rss_mib"])


def test_sample_reports_peak_rss_of_a_short_child() -> None:
    """A child that exits between polls still reports its peak from getrusage."""
    script = "b = bytearray(96 * 2**20); b[::4096] = b'x' * len(b[::4096])"
    assert (_sample_peak_mib(sys.executable, "-c", script) or 0) >= PEAK_FLOOR_MIB


def test_sample_ignores_the_footprint_a_child_inherits() -> None:
    """A tiny command does not report the sampler's own memory as its peak."""
    peak = _sample_peak_mib("true")
    assert peak is None or peak < TINY_MIB


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
