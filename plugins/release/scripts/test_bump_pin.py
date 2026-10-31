"""Tests for bump_pin.py."""

# ruff: noqa: S101, INP001, D103, PLR2004
import os
import pathlib
from typing import TYPE_CHECKING

import bump_pin
import pytest

if TYPE_CHECKING:
    from typing import NoReturn


def test_inline_array_and_name_casing(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "pyproject.toml"
    f.write_text(
        '[project]\ndependencies = ["Foo_Bar[x]==0.1.1", "other==0.1.1", "foo-bar==0.1.10"]\n'
    )
    assert bump_pin.bump(f, "foo-bar", "0.1.1", "0.2.0") == 1
    assert f.read_text() == (
        '[project]\ndependencies = ["Foo_Bar[x]==0.2.0", "other==0.1.1", "foo-bar==0.1.10"]\n'
    )


def test_toml_edits_only_dependency_arrays(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "pyproject.toml"
    before = (
        "[project]\n"
        'description = """multi\nline foo==1.0.0"""\n'
        'dependencies = [\n  "foo==1.0.0",  # foo==1.0.0\n]\n'
        "[project.optional-dependencies]\n"
        "dev = [\"foo==1.0.0; python_version >= '3.9'\"]\n"
        "[dependency-groups]\n"
        'test = ["foo==1.0.0", {include-group = "dev"}]\n'
        "[tool.docs]\n"
        'example = "foo==1.0.0"\n'
        "# foo==1.0.0\n"
    )
    f.write_bytes(before.replace("\n", "\r\n").encode())
    assert bump_pin.bump(f, "foo", "1.0.0", "1.1.0") == 3
    after = f.read_bytes().decode()
    assert after.count("foo==1.1.0") == 3
    assert after.count("foo==1.0.0") == 4
    assert 'example = "foo==1.0.0"' in after
    assert "# foo==1.0.0\r\n" in after


def test_toml_dependency_array_with_multiline_string_is_refused(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "pyproject.toml"
    before = '[project]\ndependencies = ["""foo==1.0.0"""]\n'
    f.write_text(before)
    assert bump_pin.main([str(f), "foo", "1.0.0", "1.1.0"]) == 3
    assert f.read_text() == before


def test_json_edits_only_dependency_sections(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "package.json"

    def document(prefix: str, version: str) -> str:
        deps = f'"dependencies": {{"foo": "{prefix}{version}", "foo-x": "1.0.0"}}'
        dev = f'"devDependencies": {{"foo": "{version}"}}'
        other = '"config": {"foo": "1.0.0"}, "scripts": {"foo": "1.0.0"}'
        return f"{{{other}, {deps},\n {dev}}}\n"

    f.write_text(document("^", "1.0.0"))
    assert bump_pin.bump(f, "foo", "1.0.0", "1.1.0") == 2
    assert f.read_text() == document("^", "1.1.0")


def test_json_duplicate_keys_are_refused(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "package.json"
    before = '{"dependencies": {"foo": "1.0.0", "foo": "1.0.0"}}'
    f.write_text(before)
    assert bump_pin.main([str(f), "foo", "1.0.0", "1.1.0"]) == 3
    assert f.read_text() == before


def test_requirements_file_comments_options_and_prerelease_boundary(
    tmp_path: pathlib.Path,
) -> None:
    f = tmp_path / "requirements.txt"
    f.write_text("foo==0.1.1a1\nfoo==0.1.1  # foo==0.1.1\n# foo==0.1.1\n--hash=foo==0.1.1\n")
    assert bump_pin.bump(f, "foo", "0.1.1", "0.1.2") == 1
    assert f.read_text() == (
        "foo==0.1.1a1\nfoo==0.1.2  # foo==0.1.1\n# foo==0.1.1\n--hash=foo==0.1.1\n"
    )


def test_unsupported_manifest_is_refused(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "setup.cfg"
    f.write_text("foo==1.0.0\n")
    assert bump_pin.main([str(f), "foo", "1.0.0", "1.1.0"]) == 3
    assert f.read_text() == "foo==1.0.0\n"


def test_hash_pinned_requirement_is_refused_not_half_edited(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "requirements.txt"
    before = "foo==1.0.0 \\\n    --hash=sha256:abc\nbar==1.0.0 --hash=sha256:def\n"
    f.write_text(before)
    for name in ("foo", "bar"):
        assert bump_pin.main([str(f), name, "1.0.0", "1.1.0"]) == 3
    err = capsys.readouterr().err
    assert err.count("carries --hash digests") == 2
    assert err.count("Nothing was written.") == 2
    assert f.read_text() == before


def test_refusal_says_nothing_was_written_and_names_supported_manifests(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "Cargo.toml"
    f.write_text('[dependencies]\nfoo = "=1.0.0"\n')
    assert bump_pin.main([str(f), "foo", "1.0.0", "1.1.0"]) == 3
    err = capsys.readouterr().err
    assert "unsupported manifest Cargo.toml" in err
    assert "Nothing was written." in err
    assert "may have changed" not in err


def test_package_json_scoped_name(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "package.json"
    f.write_text('{"dependencies": {"@s/pkg": "~1.0.0"}}\n')
    assert bump_pin.bump(f, "@s/pkg", "1.0.0", "1.1.0") == 1
    assert '"~1.1.0"' in f.read_text()


def test_change_during_preparation_writes_nothing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "requirements.txt"
    f.write_text("foo==1.0.0\n")
    real = bump_pin.edit

    def racing(manifest: pathlib.Path, *args: str) -> tuple[str, int]:
        result = real(manifest, *args)
        manifest.write_text("foo==1.0.0\n# concurrent\n")
        return result

    monkeypatch.setattr(bump_pin, "edit", racing)
    assert bump_pin.main([str(f), "foo", "1.0.0", "1.1.0"]) == 3
    assert f.read_text() == "foo==1.0.0\n# concurrent\n"
    assert [p.name for p in tmp_path.iterdir()] == ["requirements.txt"]


def test_pin_edit_preserves_other_bytes_and_mode(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "requirements.txt"
    before = "# café\r\nfoo==1.0.0\rother==9.0.0\n".encode()
    f.write_bytes(before)
    f.chmod(0o640)
    mode = f.stat().st_mode
    assert bump_pin.bump(f, "foo", "1.0.0", "1.1.0") == 1
    assert f.read_bytes() == before.replace(b"foo==1.0.0", b"foo==1.1.0")
    assert f.stat().st_mode == mode


def test_no_match_leaves_file_and_exits_1(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "pyproject.toml"
    f.write_text('[project]\ndependencies = ["foo>=0.1.1"]\n')
    assert bump_pin.main([str(f), "foo", "0.1.1", "0.2.0"]) == 1
    assert f.read_text() == '[project]\ndependencies = ["foo>=0.1.1"]\n'
    assert "edit it by hand" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["symlink", "dangling", "hardlink", "directory", "fifo"])
def test_linked_or_nonregular_leaf_refuses_before_read(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    target = tmp_path / "outside.txt"
    target.write_bytes(b"foo==1.0.0\r\n")
    target.chmod(0o640)
    manifest = tmp_path / "requirements.txt"
    if kind == "symlink":
        manifest.symlink_to(target)
    elif kind == "dangling":
        manifest.symlink_to(tmp_path / "absent")
    elif kind == "hardlink":
        os.link(target, manifest)
    elif kind == "directory":
        manifest.mkdir()
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFO creation requires os.mkfifo")
        os.mkfifo(manifest)
    before = manifest.lstat()
    target_before = target.stat()

    def forbidden_read(_path: pathlib.Path) -> NoReturn:
        pytest.fail("a refused leaf must not be opened for content")

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "read_bytes", forbidden_read)
        status = bump_pin.main([str(manifest), "foo", "1.0.0", "1.1.0"])
    assert status == 3
    assert manifest.lstat() == before
    assert target.stat() == target_before
    assert target.read_bytes() == b"foo==1.0.0\r\n"
    output = capsys.readouterr()
    assert not output.out
    assert "refus" in output.err
    assert "edit it by hand" not in output.err
    assert "untouched" not in output.err


@pytest.mark.parametrize("failure", ["lstat", "read", "decode", "replace", "missing"])
def test_file_failures_return_distinct_status_without_unchanged_claim(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    manifest = tmp_path / "requirements.txt"
    before = b"foo==1.0.0\r\n" if failure != "decode" else b"foo==1.0.0\xff"
    if failure != "missing":
        manifest.write_bytes(before)

    def failed_operation(*_args: object) -> NoReturn:
        message = "injected observation/read failure"
        raise OSError(message)

    with monkeypatch.context() as patch:
        if failure == "lstat":
            patch.setattr(pathlib.Path, "lstat", failed_operation)
        elif failure == "read":
            patch.setattr(pathlib.Path, "read_bytes", failed_operation)
        elif failure == "replace":
            patch.setattr(pathlib.Path, "replace", failed_operation)
        status = bump_pin.main([str(manifest), "foo", "1.0.0", "1.1.0"])
    assert status == 3
    output = capsys.readouterr()
    assert not output.out
    assert "pin update failed" in output.err
    assert "may have changed" in output.err
    assert "untouched" not in output.err
    assert "edit it by hand" not in output.err
    if failure == "missing":
        assert not manifest.exists()
    else:
        assert manifest.read_bytes() == before
        assert [p.name for p in tmp_path.iterdir()] == ["requirements.txt"]


@pytest.mark.parametrize("usage", [False, True])
def test_normal_no_match_and_usage_keep_distinct_statuses(
    tmp_path: pathlib.Path,
    usage: bool,
) -> None:
    manifest = tmp_path / "requirements.txt"
    before = b"other==1.0.0\r\n"
    manifest.write_bytes(before)
    metadata = manifest.stat()
    argv = [] if usage else [str(manifest), "foo", "1.0.0", "1.1.0"]
    assert bump_pin.main(argv) == (2 if usage else 1)
    assert manifest.stat().st_ino == metadata.st_ino
    assert manifest.stat().st_mode == metadata.st_mode
    assert manifest.read_bytes() == before
