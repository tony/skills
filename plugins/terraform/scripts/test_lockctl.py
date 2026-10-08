"""lockctl: lock-file state, block removal, and stable-version filtering."""

# ruff: noqa: S101, S603, S607, PLR2004, INP001, D103, TC002, TC003
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import subprocess
from pathlib import Path

import lockctl  # pyright: ignore[reportImplicitRelativeImport]
import pytest

LOCK = """provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.60.0"
  constraints = "~> 5.60"
  hashes = [
    "h1:aaa=",
    "h1:bbb=",
    "h1:ccc=",
    "zh:111",
  ]
}

provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.0"
  constraints = "~> 3.6"
  hashes = [
    "h1:ddd=",
    "zh:333",
  ]
}
"""


def test_state_counts_each_provider_separately(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = tmp_path / ".terraform.lock.hcl"
    lock.write_text(LOCK)
    assert lockctl.main(["lockctl.py", "state", str(lock)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "registry.terraform.io/hashicorp/aws\t5.60.0\t3",
        "registry.terraform.io/hashicorp/random\t3.6.0\t1",
    ]


def test_drop_leaves_the_other_block_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = tmp_path / ".terraform.lock.hcl"
    lock.write_text(LOCK)
    argv = ["lockctl.py", "drop", str(lock), "registry.terraform.io/hashicorp/aws"]
    assert lockctl.main(argv) == 0
    assert capsys.readouterr().out.strip() == "dropped"
    assert (
        lock.read_text() == LOCK[LOCK.index('provider "registry.terraform.io/hashicorp/random"') :]
    )
    assert [p.name for p in tmp_path.iterdir()] == [".terraform.lock.hcl"]


def test_drop_absent_provider_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = tmp_path / ".terraform.lock.hcl"
    lock.write_text(LOCK)
    assert lockctl.main(["lockctl.py", "drop", str(lock), "x/y/z"]) == 0
    assert capsys.readouterr().out.strip() == "absent"
    assert lock.read_text() == LOCK


def test_stable_drops_prereleases_and_sorts_numerically() -> None:
    versions = ["1.9.0", "1.10.0", "1.11.0-beta1", "1.10.2", "1.8.0"]
    assert lockctl.stable(versions, 3) == ["1.9.0", "1.10.0", "1.10.2"]


def test_platforms_scans_ci_and_task_files_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cmd = "terraform providers lock -platform=linux_amd64 -platform=darwin_arm64\n"
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "lock.yml").write_text("run: " + cmd)
    (tmp_path / "README.md").write_text(cmd)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        lockctl, "_tracked_files", lambda: [".github/workflows/lock.yml", "README.md"]
    )
    assert lockctl.main(["lockctl.py", "platforms"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        ".github/workflows/lock.yml\tlinux_amd64,darwin_arm64"
    ]


def test_platforms_includes_untracked_ci_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "new.yml").write_text(
        "run: terraform providers lock -platform=linux_amd64\n"
    )
    monkeypatch.chdir(tmp_path)
    assert lockctl.main(["lockctl.py", "platforms"]) == 0
    assert capsys.readouterr().out.splitlines() == [".github/workflows/new.yml\tlinux_amd64"]


def test_stable_rejects_a_non_integer_count(capsys: pytest.CaptureFixture[str]) -> None:
    assert lockctl.main(["lockctl.py", "stable", "three"]) == 2
    assert "Usage" in capsys.readouterr().err


def _write(path: Path, text: str) -> str:
    path.write_text(text)
    return str(path)


def test_diff_allows_the_named_provider_to_move(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _write(tmp_path / "a", LOCK)
    after = _write(tmp_path / "b", LOCK.replace("5.60.0", "5.61.0"))
    aws = "registry.terraform.io/hashicorp/aws"
    assert lockctl.main(["lockctl.py", "diff", "--allow", aws, before, after]) == 0
    assert capsys.readouterr().out.strip() == f"{aws}\tmoved\t5.60.0/3\t5.61.0/3"
    assert lockctl.main(["lockctl.py", "diff", before, after]) == 1


def test_diff_fails_on_a_count_drop_even_for_the_allowed_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    narrowed = LOCK.replace('    "h1:bbb=",\n    "h1:ccc=",\n', "").replace("5.60.0", "5.61.0")
    before = _write(tmp_path / "a", LOCK)
    after = _write(tmp_path / "b", narrowed)
    argv = ["lockctl.py", "diff", "--allow", "*", before, after]
    assert lockctl.main(argv) == 1
    assert "count-dropped\t5.60.0/3\t5.61.0/1" in capsys.readouterr().out


def test_diff_reads_a_git_object_as_the_before_side(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    lock = tmp_path / ".terraform.lock.hcl"
    lock.write_text(LOCK)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run([*run, "commit", "-qm", "lock"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    argv = ["lockctl.py", "diff", "HEAD:.terraform.lock.hcl", ".terraform.lock.hcl"]
    assert lockctl.main(argv) == 0
    assert capsys.readouterr().out == ""
    lock.write_text(LOCK.replace("3.6.0", "3.7.0"))
    assert lockctl.main(argv) == 1
