"""Tests for scholar_pins.py: local pins, throwaway checkouts, and identifier vetting."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest
import scholar_pins as pins  # pyright: ignore[reportImplicitRelativeImport]

_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def _repo(root: Path) -> Path:
    repo = root / "corpus"
    (repo / "notes").mkdir(parents=True)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), *_ID, "commit", "--quiet", "-m", "x"], check=True)
    return repo


@pytest.mark.integration
def test_local_pin_reports_commit_ref_and_push_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean checkout prints a 40-digit commit and a 7-digit ref with no tag."""
    repo = _repo(tmp_path)
    assert pins.main(["local", str(repo)]) == 0
    pin = json.loads(capsys.readouterr().out)
    assert len(pin["commit"]) == 40
    assert pin["ref"] == pin["commit"][:7]
    assert pin["tag"] == ""
    assert pin["pushed"] is False
    subprocess.run(["git", "-C", str(repo), "tag", "v1.0.0"], check=True)
    assert pins.main(["local", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["ref"] == "v1.0.0"


@pytest.mark.integration
def test_local_pin_refuses_a_dirty_tree_but_not_the_study_inside_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edits to the corpus refuse; files under the excluded study directory do not."""
    repo = _repo(tmp_path)
    (repo / "notes" / "terms.jsonl").write_text("{}\n", encoding="utf-8")
    study = repo / "notes"
    assert pins.main(["local", str(repo), "--study", str(study)]) == 0
    capsys.readouterr()
    assert pins.main(["local", str(repo)]) == 2
    assert capsys.readouterr().err == "the corpus has uncommitted edits\n"
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert pins.main(["local", str(repo), "--study", str(study)]) == 2


@pytest.mark.integration
def test_local_pin_refuses_a_checkout_at_another_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--expect`` is how ``extract`` insists HEAD is the recorded commit."""
    repo = _repo(tmp_path)
    assert pins.main(["local", str(repo), "--expect", "deadbee"]) == 2
    assert "not deadbee" in capsys.readouterr().err


def test_local_pin_refuses_a_directory_that_is_not_a_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plain directory gets the one-line reason, not a git traceback."""
    assert pins.main(["local", str(tmp_path)]) == 2
    assert "is not a git checkout" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("url", "commit"),
    [
        ("http://example.com/o/r", "a" * 40),
        ("https://example.com/o/r;rm", "a" * 40),
        ("https://example.com/o/r", "abc"),
        ("file:///etc", "a" * 40),
        ("https://example.com/o/r?x=$(id)", "a" * 40),
    ],
)
def test_remote_refuses_unsafe_sources(
    capsys: pytest.CaptureFixture[str], url: str, commit: str
) -> None:
    """Only a plain https URL and a full commit reach git."""
    assert pins.main(["remote", url, commit]) == 2
    assert (
        capsys.readouterr().err == "the source must be a plain https:// URL and a 40-digit commit\n"
    )


@pytest.mark.integration
def test_fetch_checks_out_the_commit_and_release_removes_it(tmp_path: Path) -> None:
    """The throwaway checkout holds the pinned file; ``release`` deletes only its own kind."""
    repo = _repo(tmp_path)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    path = pins.fetch(repo.as_uri(), head)
    assert (Path(path) / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert pins.main(["release", path]) == 0
    assert not Path(path).exists()


@pytest.mark.integration
def test_failed_fetch_leaves_no_directory(tmp_path: Path) -> None:
    """A fetch that fails cleans up the directory it made."""
    repo = _repo(tmp_path)
    before = set(Path(tempfile.gettempdir()).glob("scholar-corpus.*"))
    with pytest.raises(pins.FetchError, match="could not fetch"):
        pins.fetch(repo.as_uri(), "b" * 40)
    assert set(Path(tempfile.gettempdir()).glob("scholar-corpus.*")) == before


def test_release_refuses_directories_it_did_not_make(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``release`` never deletes an arbitrary path."""
    victim = tmp_path / "keep"
    victim.mkdir()
    assert pins.main(["release", str(victim)]) == 2
    assert victim.exists()
    assert capsys.readouterr().err == "keep is not a scholar checkout\n"


@pytest.mark.parametrize(
    ("flags", "reason"),
    [
        (["--owner", ".."], "owner '..' is not a GitHub owner name"),
        (["--owner", "a/b"], "owner 'a/b' is not a GitHub owner name"),
        (["--repo", "r;id"], "repo 'r;id' is not a GitHub repo name"),
        (["--ref", "../x"], "ref '../x' is not a plain relative ref"),
        (["--path", "/etc/passwd"], "path '/etc/passwd' is not a plain relative path"),
        (["--path", "a/../b"], "path 'a/../b' is not a plain relative path"),
        (["--commit", "zzz"], "commit 'zzz' is not 7 to 40 hex digits"),
        (["--url", "https://example.com/x"], "url 'https://example.com/x' is not a plain"),
        (["--url", "https://github.com/o/r/blob/v1/a.py'; id"], "is not a plain https"),
    ],
)
def test_ident_refuses_unsafe_values(
    capsys: pytest.CaptureFixture[str], flags: list[str], reason: str
) -> None:
    """Each unsafe identifier exits non-zero with its reason."""
    assert pins.main(["ident", *flags]) == 2
    assert reason in capsys.readouterr().err


def test_ident_accepts_plain_values() -> None:
    """Ordinary study values pass."""
    flags = ["--owner", "o", "--repo", "r.js", "--ref", "release/v1", "--path", "src/a.py"]
    url = "https://github.com/o/r/blob/v1/src/a.py#L1-L2"
    assert pins.main(["ident", *flags, "--commit", "a" * 40, "--url", url]) == 0


def test_sha256_matches_hashlib(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The digest is portable, unlike ``sha256sum``."""
    target = tmp_path / "f"
    target.write_bytes(b"abc")
    assert pins.main(["sha256", str(target)]) == 0
    assert capsys.readouterr().out.strip() == hashlib.sha256(b"abc").hexdigest()


@pytest.mark.integration
def test_resolve_remote_peels_annotated_tags_and_prefers_tags(tmp_path: Path) -> None:
    """An annotated tag resolves to its commit, a branch to its tip, a tag over a branch."""
    repo = _repo(tmp_path)
    git = ["git", "-C", str(repo), *_ID]
    head = subprocess.run(
        [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run([*git, "tag", "-a", "v1", "-m", "release"], check=True)
    subprocess.run([*git, "branch", "v2"], check=True)
    assert pins.resolve_remote(repo.as_uri(), "v1") == (head, True)
    assert pins.resolve_remote(repo.as_uri(), "v2") == (head, False)
    with pytest.raises(pins.FetchError, match="not found"):
        pins.resolve_remote(repo.as_uri(), "nope")


@pytest.mark.parametrize(
    ("url", "ref"),
    [("file:///etc", "v1"), ("https://example.com/o/r", "../x"), ("http://x.org/o/r", "v1")],
)
def test_ls_remote_refuses_unsafe_values(
    capsys: pytest.CaptureFixture[str], url: str, ref: str
) -> None:
    """Only a plain https URL and a plain ref reach git."""
    assert pins.main(["ls-remote", url, ref]) == 2
    assert capsys.readouterr().err == "the source must be a plain https:// URL and a plain ref\n"


def test_release_of_a_missing_checkout_is_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A scholar-named path that does not exist exits 2, not with a traceback."""
    missing = Path(tempfile.gettempdir()) / "scholar-corpus.gone"
    assert pins.main(["release", str(missing)]) == 2
    assert capsys.readouterr().err == "no checkout scholar-corpus.gone\n"
