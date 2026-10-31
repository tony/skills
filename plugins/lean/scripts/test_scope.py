"""Tests for scope.py against a throwaway repository."""

# ruff: noqa: S101, S603, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
import subprocess
from typing import TYPE_CHECKING

import scope  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

    import pytest


def _run(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S607


def test_branch_ranges_cover_only_added_lines(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Untouched lines on a changed file stay out of the ranges."""
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    f = tmp_path / "a.py"
    f.write_text("# old\nx = 1\ny = 2\n")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "-q", "-m", "base")
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    f.write_text("# old\nx = 1\ny = 2\n# new\nz = 3\n")
    _run(tmp_path, "commit", "-qam", "change")
    monkeypatch.chdir(tmp_path)

    assert scope.main([]) == 0
    assert capsys.readouterr().out == "a.py\t4-5\n"


def test_no_trunk_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A repo without a trunk ref halts instead of widening scope."""
    _run(tmp_path, "init", "-q", "-b", "dev")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 2
    assert "no trunk ref" in capsys.readouterr().err


def _topic_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    f = tmp_path / "a.py"
    f.write_text("x = 1\n# gone\ny = 2\n")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "-q", "-m", "base")
    return f


def test_all_lists_names_only(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--all prints tracked names with no ranges."""
    _topic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--all"]) == 0
    assert capsys.readouterr().out == "a.py\n"


def test_staged_and_deletion_only_range(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A deletion-only hunk prints an empty range; --staged reads the index."""
    f = _topic_repo(tmp_path)
    f.write_text("x = 1\ny = 2\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--staged"]) == 0
    assert capsys.readouterr().out == "a.py\t\n"


def test_spaced_path_has_no_trailing_tab(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A path with a space prints exactly, with no quoting tab."""
    _topic_repo(tmp_path)
    (tmp_path / "a b.py").write_text("x = 1\ny = 2\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--staged"]) == 0
    assert capsys.readouterr().out == "a b.py\t1-2\n"


def test_diff_prefix_config_is_ignored(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """diff.mnemonicPrefix and diff.noprefix do not hide changed files."""
    f = _topic_repo(tmp_path)
    f.write_text("x = 1\n# gone\ny = 2\n# new\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    for key in ("diff.mnemonicPrefix", "diff.noprefix"):
        _run(tmp_path, "config", key, "true")
        assert scope.main(["--staged"]) == 0
        assert capsys.readouterr().out == "a.py\t4-4\n"
        _run(tmp_path, "config", "--unset", key)


def test_untracked_file_counts_as_added_in_full(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A new file never passed to git add is in branch scope."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "fresh.py").write_text("# c\nx = 1\ny = 2\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "fresh.py\t1-3\n"


def test_paths_are_relative_to_cwd_from_a_subdirectory(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Diff and --all paths agree and resolve from the current directory."""
    _topic_repo(tmp_path)
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "m.py").write_text("x = 1\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(sub)
    assert scope.main(["--staged"]) == 0
    assert capsys.readouterr().out == "m.py\t1-1\n"
    assert scope.main(["--all"]) == 0
    assert capsys.readouterr().out == "../a.py\nm.py\n"


def _commit_file(repo: pathlib.Path, name: str) -> None:
    (repo / name).write_text("x = 1\n")
    _run(repo, "add", ".")
    _run(repo, "commit", "-q", "-m", name)


def test_orphan_branch_exits_2_without_traceback(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An orphan branch shares no history with the trunk."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "--orphan", "island")
    _commit_file(tmp_path, "b.py")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 2
    assert "no merge base with main" in capsys.readouterr().err


def test_shallow_clone_without_merge_base_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A depth-1 clone of a diverged branch cannot reach the merge base."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _topic_repo(origin)
    _run(origin, "checkout", "-q", "-b", "topic")
    _commit_file(origin, "t1.py")
    _run(origin, "checkout", "-q", "main")
    _commit_file(origin, "m1.py")
    clone = tmp_path / "clone"
    _run(
        tmp_path,
        "clone",
        "-q",
        "--depth=1",
        "--no-single-branch",
        origin.as_uri(),
        str(clone),
    )
    _run(clone, "checkout", "-q", "topic")
    monkeypatch.chdir(clone)
    assert scope.main([]) == 2
    assert "no merge base" in capsys.readouterr().err


def test_untracked_symlink_to_directory_is_skipped(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A symlinked directory is not a readable file and never crashes."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "pkg", target_is_directory=True)
    (tmp_path / "fresh.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "fresh.py\t1-1\n"


def test_untracked_file_without_trailing_newline_counts_last_line(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A final line lacking a newline is still in range."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "m.py").write_text("x = 1\n# c\n# d")
    (tmp_path / "n.py").write_text("# c")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "m.py\t1-3\nn.py\t1-1\n"


def test_outside_a_repo_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No repository halts with a message, not a traceback."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 2
    assert "not inside a git repository" in capsys.readouterr().err


def test_unstaged_edit_on_topic_branch_is_in_scope(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An uncommitted edit to a tracked file counts in branch mode."""
    f = _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    f.write_text("x = 1\n# gone\ny = 2\n# new\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "a.py\t4-4\n"


def test_origin_head_sets_the_trunk(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The remote default branch wins over a local main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _topic_repo(origin)
    clone = tmp_path / "clone"
    _run(tmp_path, "clone", "-q", origin.as_uri(), str(clone))
    _run(clone, "config", "user.email", "t@example.com")
    _run(clone, "config", "user.name", "t")
    _run(clone, "checkout", "-q", "-b", "topic")
    _commit_file(clone, "t.py")
    monkeypatch.chdir(clone)
    assert scope.trunk_ref() == "origin/main"
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "t.py\t1-1\n"


def test_dangling_origin_head_falls_through_to_main(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An origin/HEAD pointing at a missing ref does not mask origin/main or main."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    _commit_file(tmp_path, "t.py")
    _run(tmp_path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/nope")
    monkeypatch.chdir(tmp_path)
    assert scope.trunk_ref() == "main"
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "t.py\t1-1\n"


def test_tab_in_untracked_name_is_listed(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A control character in a name never drops the file silently."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "a\tb.py").write_text("x = 1\n")
    (tmp_path / "c.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == "a\tb.py\t1-1\nc.py\t1-1\n"


def test_tab_in_tracked_name_is_listed(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A quoted diff header decodes back to the real name."""
    _topic_repo(tmp_path)
    (tmp_path / "a\tb.py").write_text("x = 1\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--staged"]) == 0
    assert capsys.readouterr().out == "a\tb.py\t1-1\n"


def test_binary_untracked_file_is_reported_not_listed(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A binary untracked file is named on stderr and left out."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "blob.bin").write_bytes(b"\0\1\2")
    (tmp_path / "c.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    out = capsys.readouterr()
    assert out.out == "c.py\t1-1\n"
    assert "blob.bin" in out.err


def test_lockfiles_and_vendored_trees_are_left_out(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lockfiles, vendored dirs, and linguist-generated files never reach the list."""
    _topic_repo(tmp_path)
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    (tmp_path / "uv.lock").write_text("x\n")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "v.py").write_text("x = 1\n")
    (tmp_path / "gen.py").write_text("x = 1\n")
    (tmp_path / ".gitattributes").write_text("gen.py linguist-generated\n")
    (tmp_path / "keep.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 0
    assert capsys.readouterr().out == ".gitattributes\t1-1\nkeep.py\t1-1\n"


def test_paths_resolve_tracked_globs_and_untracked_literals(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--paths tags each file tracked or untracked; a miss exits 2."""
    _topic_repo(tmp_path)
    (tmp_path / "new.md").write_text("hi\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--paths", "*.py", "new.md"]) == 0
    assert capsys.readouterr().out == "a.py\ttracked\nnew.md\tuntracked\n"
    assert scope.main(["--paths", "missing.md"]) == 2
    assert "not a file: missing.md" in capsys.readouterr().err


def test_paths_glob_matches_tracked_and_untracked(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A glob lists untracked matches beside tracked ones."""
    _topic_repo(tmp_path)
    (tmp_path / "new.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--paths", "*.py"]) == 0
    assert capsys.readouterr().out == "a.py\ttracked\nnew.py\tuntracked\n"


def test_paths_marks_a_tracked_file_deleted_from_the_worktree(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tracked file removed from disk is reported deleted, not tracked."""
    f = _topic_repo(tmp_path)
    f.unlink()
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--paths", "a.py"]) == 0
    assert capsys.readouterr().out == "a.py\tdeleted\n"
