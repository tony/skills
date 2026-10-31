"""lockctl: lock-file state, block removal, and stable-version filtering."""

# ruff: noqa: S101, S603, S607, PLR2004, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import re
import shlex
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


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_drop_leaves_the_other_block_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], newline: str
) -> None:
    lock = tmp_path / ".terraform.lock.hcl"
    original = LOCK.replace("\n", newline).encode()
    lock.write_bytes(original)
    argv = ["lockctl.py", "drop", str(lock), "registry.terraform.io/hashicorp/aws"]
    assert lockctl.main(argv) == 0
    assert capsys.readouterr().out.strip() == "dropped"
    other = b'provider "registry.terraform.io/hashicorp/random"'
    assert lock.read_bytes() == original[original.index(other) :]
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


@pytest.mark.integration
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


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("h1:ddd=", "h1:unexpected="),
        ('    "zh:333",\n', ""),
        ("~> 3.6", "= 3.6.0"),
        ("\n", "\r\n"),
    ],
)
def test_diff_rejects_other_block_content_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], old: str, new: str
) -> None:
    before = _write(tmp_path / "a", LOCK)
    after = _write(tmp_path / "b", LOCK.replace("5.60.0", "5.61.0").replace(old, new))
    aws = "registry.terraform.io/hashicorp/aws"
    random = "registry.terraform.io/hashicorp/random"
    assert lockctl.main(["lockctl.py", "diff", "--allow", aws, before, after]) == 1
    assert f"{random}\tchanged\t3.6.0/1\t3.6.0/1" in capsys.readouterr().out
    assert lockctl.main(["lockctl.py", "diff", "--allow", "*", before, after]) == 0


@pytest.mark.integration
def test_diff_reads_a_git_object_as_the_before_side(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = [
        "git",
        "-c",
        "core.autocrlf=false",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    lock = tmp_path / ".terraform.lock.hcl"
    original = LOCK.replace("\n", "\r\n").encode()
    lock.write_bytes(original)
    subprocess.run([*run, "add", "."], cwd=tmp_path, check=True)
    subprocess.run([*run, "commit", "-qm", "lock"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    argv = ["lockctl.py", "diff", "HEAD:.terraform.lock.hcl", ".terraform.lock.hcl"]
    assert lockctl.main(argv) == 0
    assert capsys.readouterr().out == ""
    for edited in (
        original.replace(b"3.6.0", b"3.7.0"),
        original.replace(b"h1:ddd=", b"h1:unexpected="),
        original.replace(b"\r\n", b"\n"),
    ):
        lock.write_bytes(edited)
        assert lockctl.main(argv) == 1
        assert "registry.terraform.io/hashicorp/random\tchanged" in capsys.readouterr().out


@pytest.mark.integration
def test_configuration_searches_include_tofu_json(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "infra/json").mkdir(parents=True)
    (tmp_path / "modules/policy").mkdir(parents=True)
    (tmp_path / "infra/json/main.tofu.json").write_text(
        """{"terraform":{"backend":{"local":{}},"required_version":"= 1.10.0"},
"module":{"policy":{"source":"../../modules/policy"}}}
"""
    )
    (tmp_path / "modules/policy/versions.tofu.json").write_text(
        """{"terraform":{"required_providers":{"random":
{"source":"hashicorp/random","version":"~> 3.6"}}}}
"""
    )
    subprocess.run(["git", "add", "infra", "modules"], cwd=tmp_path, check=True)
    plugin = Path(__file__).resolve().parents[1]
    checked = 0
    for relative in (
        "references/layout-discovery.md",
        "references/pin-sites.md",
        "skills/bump-provider/SKILL.md",
    ):
        for command in re.findall(
            r"```console\n\$ (.*?)\n```", (plugin / relative).read_text(), re.DOTALL
        ):
            argv = shlex.split(command.replace("\\\n", " "))
            if argv[:2] not in (["git", "ls-files"], ["git", "grep"]) or "*.tf" not in argv:
                continue
            result = subprocess.run(argv, cwd=tmp_path, capture_output=True, check=True)
            assert b".tofu.json" in result.stdout, (relative, command)
            checked += 1
    assert checked == 5
