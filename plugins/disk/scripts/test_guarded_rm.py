"""Delete guard: scope, keeper, and symlink refusals."""

# ruff: noqa: S101, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import os
import shutil
import subprocess
import sys
from pathlib import Path

import guarded_rm  # pyright: ignore[reportImplicitRelativeImport]
import pytest

REFUSED = guarded_rm.EXIT_REFUSED
OK = guarded_rm.EXIT_OK


@pytest.fixture(autouse=True)
def clear_open_handle_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def which(name: str) -> str | None:
        return name if name == "lsof" else None

    def probe(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 1, b"", b"")

    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.setattr(subprocess, "run", probe)


def run(*args: str) -> int:
    return guarded_rm.main(["guarded_rm.py", *args])


def test_listing_without_delete_keeps_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "s" / "cache").mkdir(parents=True)
    (tmp_path / "s" / "cache" / "f").write_text("x")
    assert run("--scope", str(tmp_path / "s"), str(tmp_path / "s" / "cache")) == OK
    assert "  f" in capsys.readouterr().out
    assert (tmp_path / "s" / "cache" / "f").exists()


def test_delete_removes_target_only(tmp_path: Path) -> None:
    (tmp_path / "s" / "cache").mkdir(parents=True)
    (tmp_path / "s" / "cache" / "f").write_text("x")
    (tmp_path / "s" / "other").write_text("y")
    args = ["--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s" / "cache")]
    assert run(*args) == OK
    assert not (tmp_path / "s" / "cache").exists()
    assert (tmp_path / "s" / "other").exists()


def test_symlink_out_of_scope_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "precious").write_text("x")
    (tmp_path / "s" / "link").symlink_to(tmp_path / "out")
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s" / "link")) == REFUSED
    assert (tmp_path / "out" / "precious").exists()


def test_scope_root_and_outside_are_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    (tmp_path / "o").mkdir()
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s")) == REFUSED
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "o")) == REFUSED
    assert (tmp_path / "s").exists()
    assert (tmp_path / "o").exists()


@pytest.mark.parametrize("target_name", ["homes", "homes/user"])
def test_home_and_ancestors_are_refused_with_broader_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str
) -> None:
    home = tmp_path / "homes" / "user"
    home.mkdir(parents=True)
    payload = home / "only-copy"
    payload.write_text("keep")

    def home_directory(_cls: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(home_directory))
    assert run("--scope", str(tmp_path), "--delete", str(tmp_path / target_name)) == REFUSED
    assert payload.read_text() == "keep"


@pytest.mark.parametrize(
    "target_name",
    [".claude/projects", ".claude/projects/proj", ".codex/sessions/2026", ".claude", ".codex"],
)
def test_agent_history_is_refused_unless_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str
) -> None:
    home = tmp_path / "home"
    (home / ".claude" / "projects" / "proj").mkdir(parents=True)
    (home / ".codex" / "sessions" / "2026").mkdir(parents=True)
    target = home / target_name

    def home_directory(_cls: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(home_directory))
    scope = str(tmp_path)
    assert run("--scope", scope, "--delete", str(target)) == REFUSED
    assert target.exists()
    if target_name.count("/"):
        assert run("--scope", scope, "--allow-history", "--delete", str(target)) == OK
        assert not target.exists()


def test_keeper_overlap_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s" / "a" / "keep").mkdir(parents=True)
    scope = str(tmp_path / "s")
    keeper = str(tmp_path / "s" / "a" / "keep")
    assert (
        run("--scope", scope, "--keeper", keeper, "--delete", str(tmp_path / "s" / "a")) == REFUSED
    )
    assert run("--scope", scope, "--keeper", keeper, "--delete", keeper) == REFUSED
    assert (tmp_path / "s" / "a" / "keep").exists()


def test_missing_target_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    assert run("--scope", str(tmp_path / "s"), str(tmp_path / "s" / "nope")) == REFUSED


def test_refuses_mount_point_inside_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "s" / "cache"
    (cache / "mnt").mkdir(parents=True)
    real_lstat = os.lstat

    def fake_lstat(path: str) -> object:
        st = real_lstat(path)
        if str(path).endswith("mnt"):
            fields = list(st)
            fields[2] += 1
            return os.stat_result(fields)
        return st

    monkeypatch.setattr(os, "lstat", fake_lstat)
    assert run("--scope", str(tmp_path / "s"), "--delete", str(cache)) == REFUSED
    assert (cache / "mnt").exists()


def test_sub_gib_sizes_use_mib_and_kib() -> None:
    assert guarded_rm.human(8 * 1024) == "8 KiB"
    assert guarded_rm.human(3 * 2**20) == "3.0 MiB"
    assert guarded_rm.human(2 * 2**30) == "2.00 GiB"


def test_mount_point_as_target_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    payload = target / "only-copy"
    payload.write_text("keep")
    real = os.path.ismount

    def mounted(path: str | os.PathLike[str]) -> bool:
        return str(path) == str(target) or real(path)

    monkeypatch.setattr(os.path, "ismount", mounted)
    assert run("--scope", str(tmp_path), "--delete", str(target)) == REFUSED
    assert payload.read_text() == "keep"


def test_same_device_bind_mount_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "cache"
    mount = target / "mounted store"
    mount.mkdir(parents=True)
    payload = mount / "only-copy"
    payload.write_text("keep")
    real_read = Path.read_text
    escaped = str(mount).replace(" ", r"\040")

    def mount_table(path: Path, *args: object, **kwargs: object) -> str:
        if str(path) == "/proc/self/mountinfo":
            return f"1 0 8:1 / {escaped} rw - ext4 /dev/test rw\n"
        return real_read(path, *args, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", mount_table)
    assert run("--scope", str(tmp_path), "--delete", str(target)) == REFUSED
    assert payload.read_text() == "keep"


def test_unreadable_subtree_refuses_before_deleting_readable_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "cache"
    locked = target / "locked"
    locked.mkdir(parents=True)
    payload = target / "keep"
    payload.write_text("keep")
    real = os.scandir

    def denied(path: str | os.PathLike[str]) -> object:
        if str(path) == str(locked):
            raise PermissionError
        return real(path)

    monkeypatch.setattr(os, "scandir", denied)
    assert run("--scope", str(tmp_path), "--delete", str(target)) == REFUSED
    assert payload.read_text() == "keep"


@pytest.mark.parametrize(
    ("probe_result", "expected"),
    [((0, b"123", b""), REFUSED), ((1, b"", b"incomplete"), REFUSED), ((1, b"", b""), OK)],
)
def test_open_handle_probe_must_finish_before_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_result: tuple[int, bytes, bytes],
    expected: int,
) -> None:
    target = tmp_path / "cache"
    nested = target / "nested"
    nested.mkdir(parents=True)
    payload = nested / "résumé data"
    payload.write_text("keep")
    calls: list[list[str]] = []
    code, stdout, stderr = probe_result

    def probe(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert payload.read_text() == "keep"
        assert kwargs["timeout"] == guarded_rm.LSOF_TIMEOUT
        calls.append(command)
        assert command == ["lsof", "-nP", "+w", "+D", str(target)]
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    monkeypatch.setattr(shutil, "which", str)
    monkeypatch.setattr(subprocess, "run", probe)
    assert run("--scope", str(tmp_path), "--delete", str(target)) == expected
    assert [call[0] for call in calls] == ["lsof"]
    assert target.exists() == (expected == REFUSED)
    if expected == REFUSED:
        assert payload.read_text() == "keep"


def test_missing_open_handle_tools_refuses_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "cache"
    target.mkdir()

    def missing(_name: str) -> None:
        return None

    monkeypatch.setattr(shutil, "which", missing)
    assert run("--scope", str(tmp_path), "--delete", str(target)) == REFUSED
    assert target.exists()


@pytest.mark.parametrize(
    ("available", "reported"),
    [
        ((10, 6), "-4 KiB; cause not checked"),
        ((10, 14), "+4 KiB; cause not checked"),
        ((10, 10), "0 KiB; cause not checked"),
        ((10, None), "unmeasured"),
        ((None, None), "REFUSED - could not measure filesystem free space"),
    ],
)
def test_deletion_reports_only_observed_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    available: tuple[int | None, int | None],
    reported: str,
) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    payload = target / "payload"
    payload.write_bytes(b"owned fixture")
    calls = 0

    def measure(path: str) -> os.statvfs_result:
        nonlocal calls
        assert path == str(tmp_path)
        assert payload.exists() == (calls == 0)
        value = available[calls]
        calls += 1
        if value is None:
            raise OSError
        return os.statvfs_result((1024, 1024, 100, value, value, 0, 0, 0, 0, 0))

    monkeypatch.setattr(os, "statvfs", measure)
    expected = REFUSED if available[0] is None else OK
    assert run("--scope", str(tmp_path), "--delete", str(target)) == expected
    assert reported in capsys.readouterr().out
    if expected == REFUSED:
        assert payload.read_bytes() == b"owned fixture"
    else:
        assert not payload.exists()


def test_nested_approved_target_previews_and_deletes_the_same_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scope = tmp_path / "home"
    nested = scope / ".cache" / "thumbnails" / "large"
    nested.mkdir(parents=True)
    (nested / "thumb-1.png").write_bytes(b"\0" * 4096)
    sibling = scope / ".cache" / "thumbnails" / "small"
    sibling.mkdir()
    (sibling / "thumb-2.png").write_bytes(b"keep")
    unique = scope / "old-experiments" / "notes.txt"
    unique.parent.mkdir()
    unique.write_text("keep")
    assert run("--scope", str(scope), str(nested)) == OK
    assert run("--scope", str(scope), "--delete", str(nested)) == OK
    targets = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("target: ")]
    assert targets == [f"target: {nested.resolve()}"] * 2
    assert not nested.exists()
    assert (sibling / "thumb-2.png").read_bytes() == b"keep"
    assert unique.read_text() == "keep"
