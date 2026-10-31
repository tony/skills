"""Tests for default_delta.py against a fake ruff executable and real ruff."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
import shutil
import subprocess
from typing import TYPE_CHECKING

import default_delta  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib

FAKE = """#!/bin/sh
case "$*" in
  *--version*) echo 'ruff 9.9.9' ;;
  *--statistics*)
    if grep -q extend-select pyproject.toml; then
      echo '[{"code":"F401","count":4},{"code":"E401","count":1}]'
    else
      echo '[{"code":"F401","count":1}]'
    fi ;;
  *) printf '[{"code":"F401","filename":"%s/app.py","location":{"row":1,"column":8}}]' "$PWD" ;;
esac
"""

GUARD = """#!/bin/sh
[ "$1" = check ] || { echo 'ruff 9.9.9'; exit 0; }
for flag in --no-fix --no-fix-only; do
  case " $* " in
    *" $flag "*) ;;
    *) printf 'fixed\\n' > app.py ;;
  esac
done
if [ -n "${RUFF_OUTPUT_FILE:-}" ]; then
  printf 'redirected\\n' > "$RUFF_OUTPUT_FILE"
fi
"""

needs_git = pytest.mark.integration


def _fake(directory: pathlib.Path, body: str = FAKE) -> str:
    exe = directory / "ruff"
    exe.write_text(body)
    exe.chmod(0o755)
    return str(exe)


def _repo(path: pathlib.Path, config: str) -> None:
    (path / "pyproject.toml").write_text(config)
    (path / "app.py").write_text("import os\n")
    subprocess.run(["git", "init", "-q", str(path)], check=True)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('[tool.ruff.lint]\nselect = ["E"]\n', '[tool.ruff.lint]\nextend-select = ["E"]\n'),
        (
            '[tool.flake8]\nselect = ["E"]\n[tool.ruff.lint]\nselect = [\n  "E", # why\n]\n',
            '[tool.flake8]\nselect = ["E"]\n[tool.ruff.lint]\nextend-select = [\n  "E", # why\n]\n',
        ),
        (
            '[tool.ruff.lint]\nselect = ["E", # why\n]\nextend-select = ["I"]\n',
            '[tool.ruff.lint]\n\nextend-select = [\n"E", # why\n"I"]\n',
        ),
    ],
)
def test_select_becomes_extend_select(before: str, after: str) -> None:
    """Only ruff's own select is rewritten; an existing extend-select absorbs it."""
    assert default_delta.adopt_defaults(before, pyproject=True) == after


def test_inline_select_is_unsupported() -> None:
    """A shape the rewrite cannot reach stops the measurement."""
    with pytest.raises(default_delta.UnsupportedError):
        default_delta.adopt_defaults('lint = { select = ["E"] }\n', pyproject=False)


def test_equal_count_with_moved_finding_is_new() -> None:
    """A finding at a new location is new even when the code's count is unchanged."""
    old = [["a.py", "F401", 1, 8], ["a.py", "E711", 5, 4]]
    new = [["b.py", "F401", 1, 8], ["a.py", "E711", 5, 4]]
    assert default_delta.new_findings(old, new) == [("F401", 1, 1, 1)]


@pytest.mark.parametrize("mode", ["snapshot", "new-since", pytest.param("delta", marks=needs_git)])
def test_measurement_preserves_files(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Every mode disables fixes and inherited output redirection."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo, '[tool.ruff.lint]\nselect = ["F"]\n')
    report = tmp_path / "report.txt"
    report.write_text("keep the report\n")
    saved = tmp_path / "snapshot.json"
    saved.write_text('{"version": "ruff 9.9.9", "findings": []}')
    exe = _fake(tmp_path, GUARD + FAKE.partition("\n")[2])
    before = {path: path.read_bytes() for path in (repo / "app.py", report)}
    monkeypatch.setenv("RUFF_OUTPUT_FILE", str(report))
    flag = {"snapshot": ["--snapshot", str(saved)], "new-since": ["--new-since", str(saved)]}
    args = ["--cwd", str(repo), *flag.get(mode, []), "--", exe]

    assert default_delta.main(args) == 0

    assert {path: path.read_bytes() for path in before} == before


@needs_git
def test_delta_measures_the_proposed_configuration(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The proposed tree is a scratch copy; the checkout keeps its select."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo, '[tool.ruff.lint]\nselect = ["F"]\n')
    exe = _fake(tmp_path)
    assert default_delta.main(["--cwd", str(repo), "--", exe]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "E401\t0\t1\t1",
        "F401\t1\t4\t3",
        "total\t1\t5\t4",
    ]
    assert 'select = ["F"]' in (repo / "pyproject.toml").read_text()


def test_new_since_reports_only_new_locations(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The snapshot holds the old finding; a different location is reported."""
    saved = tmp_path / "snapshot.json"
    old = _fake(tmp_path)
    assert default_delta.main(["--cwd", str(tmp_path), "--snapshot", str(saved), "--", old]) == 0
    new = _fake(tmp_path, FAKE.replace('"row":1', '"row":2'))
    assert default_delta.main(["--cwd", str(tmp_path), "--new-since", str(saved), "--", new]) == 0
    assert capsys.readouterr().out.splitlines() == ["F401\t1\t1\t1"]


def test_ruff_failure_exits_2(tmp_path: pathlib.Path) -> None:
    """A ruff error is a failed measurement, never an empty result."""
    exe = _fake(tmp_path, "#!/bin/sh\nexit 2\n")
    with pytest.raises(SystemExit) as stop:
        default_delta.main(["--cwd", str(tmp_path), "--snapshot", str(tmp_path / "s"), "--", exe])
    assert stop.value.code == 2


@needs_git
@pytest.mark.skipif(shutil.which("ruff") is None, reason="needs a ruff binary")
def test_real_ruff_keeps_retained_ignores(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Adopting the defaults must not re-enable a rule the project ignores."""
    _repo(tmp_path, '[tool.ruff.lint]\nselect = ["E4"]\nignore = ["F"]\n')
    (tmp_path / "app.py").write_text("import sys\nimport os\n")
    assert default_delta.main(["--cwd", str(tmp_path), "--", "ruff"]) == 0
    codes = {line.split("\t")[0] for line in capsys.readouterr().out.splitlines()}
    assert codes == {"I001", "total"}


def test_notebook_cells_with_equal_locations_are_distinct() -> None:
    """Two cells can report one row and column; the cell index tells them apart."""
    row = '{"code":"F401","filename":"/r/n.ipynb","location":{"row":1,"column":8},"cell":%d}'
    one = default_delta.findings(f"[{row % 1}]", "/r")
    two = default_delta.findings(f"[{row % 1},{row % 2}]", "/r")
    assert default_delta.new_findings(one, two) == [("F401", 1, 2, 1)]


@needs_git
def test_symlinked_config_is_not_written_through(tmp_path: pathlib.Path) -> None:
    """The measurement rewrites a scratch copy, never the file a symlink points at."""
    outside = tmp_path / "outside.toml"
    outside.write_text('[lint]\nselect = ["F"]\n')
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("import os\n")
    (repo / "ruff.toml").symlink_to(outside)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    exe = _fake(tmp_path, FAKE.replace("pyproject.toml", "ruff.toml"))
    assert default_delta.main(["--cwd", str(repo), "--", exe]) == 0
    assert outside.read_text() == '[lint]\nselect = ["F"]\n'


@needs_git
def test_apply_writes_the_measured_rewrite(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--apply edits the extended file too and names every file it changed."""
    (tmp_path / "ruff.toml").write_text('extend = "base.toml"\n[lint]\nselect = ["F"]\n')
    (tmp_path / "base.toml").write_text('[lint]\nselect = ["E"]\n')
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert default_delta.main(["--cwd", str(tmp_path), "--apply"]) == 0
    assert capsys.readouterr().out.splitlines() == ["base.toml", "ruff.toml"]
    assert 'extend-select = ["F"]' in (tmp_path / "ruff.toml").read_text()
    assert 'extend-select = ["E"]' in (tmp_path / "base.toml").read_text()


@needs_git
def test_apply_refuses_a_symlinked_config(tmp_path: pathlib.Path) -> None:
    """A symlink would write outside the repository, so --apply stops."""
    outside = tmp_path / "outside.toml"
    outside.write_text('[lint]\nselect = ["F"]\n')
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ruff.toml").symlink_to(outside)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert default_delta.main(["--cwd", str(repo), "--apply"]) == 2
    assert outside.read_text() == '[lint]\nselect = ["F"]\n'


@needs_git
def test_extend_outside_the_repository_exits_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A configuration extending a file outside the repository cannot be measured."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ruff.toml").write_text('extend = "../shared.toml"\n')
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    exe = _fake(tmp_path)
    assert default_delta.main(["--cwd", str(repo), "--", exe]) == 2
    assert "outside the repository" in capsys.readouterr().err


@needs_git
def test_non_git_cwd_exits_2(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Without a repository there is nothing to copy, so the run refuses."""
    exe = _fake(tmp_path)
    assert default_delta.main(["--cwd", str(tmp_path), "--", exe]) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_cwd_is_required() -> None:
    """A call that omits --cwd must not fall back to the shell's directory."""
    with pytest.raises(SystemExit) as stop:
        default_delta.main(["--snapshot", "x", "--", "ruff"])
    assert stop.value.code == 2


@needs_git
def test_apply_refusal_changes_nothing(tmp_path: pathlib.Path) -> None:
    """An inline select at the root stops --apply before the plain sub-config is written."""
    (tmp_path / "ruff.toml").write_text('lint = { select = ["E"] }\n')
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "ruff.toml").write_text('[lint]\nselect = ["F"]\n')
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert default_delta.main(["--cwd", str(tmp_path), "--apply"]) == 2
    assert (sub / "ruff.toml").read_text() == '[lint]\nselect = ["F"]\n'
