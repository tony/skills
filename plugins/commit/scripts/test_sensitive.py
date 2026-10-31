"""Tests for sensitive.py against a temp repository."""

# ruff: noqa: S101, INP001, S603, S607
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("sensitive.py")
KEY = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _scan(cwd: Path, *args: str) -> tuple[int, dict[str, tuple[str, str, str]]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "scan", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    rows = [line.split("\t") for line in done.stdout.splitlines()]
    return done.returncode, {r[2]: (r[0], r[1], r[3]) for r in rows}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Build a repository with one commit."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "core.excludesFile", "/dev/null")
    _git(tmp_path, "config", "user.name", "demo")
    _git(tmp_path, "config", "user.email", "demo@example.invalid")
    (tmp_path / "app.py").write_text("a = 1\n")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        "terraform.tfstate",
        "dev/.htpasswd",
        "secrets.gpg",
        "kubeconfig",
        ".docker/config.json",
        "service-credentials.json",
        "id_ed25519",
    ],
)
def test_untracked_sensitive_names_are_refused(repo: Path, name: str) -> None:
    """Each listed name is refused without failing the run (nothing staged)."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n")
    code, rows = _scan(repo)
    assert code == 0
    assert rows[name][0] == "refuse"
    assert rows[name][2].startswith("name:")


def test_exempt_names_pass(repo: Path) -> None:
    """Example, sample and public-key files are not sensitive."""
    for name in (".env.example", "app.tfvars.sample", "id_rsa.pub"):
        (repo / name).write_text("x\n")
    _, rows = _scan(repo)
    assert {v[0] for v in rows.values()} == {"ok"}


def test_staged_content_marker_blocks_and_hides_value(repo: Path) -> None:
    """An ordinary name holding a private key refuses with exit 1."""
    (repo / "deploy.py").write_text(KEY)
    _git(repo, "add", "deploy.py")
    code, rows = _scan(repo)
    assert code == 1
    assert rows["deploy.py"] == ("refuse", "staged", "content:private-key")


def test_partial_state_and_unstaged_content(repo: Path) -> None:
    """A path with staged and unstaged edits is partial; unstaged keys are refused."""
    (repo / "app.py").write_text("a = 2\n")
    _git(repo, "add", "app.py")
    (repo / "app.py").write_text("a = 3\n")
    (repo / "new.py").write_text(KEY)
    code, rows = _scan(repo)
    assert code == 0
    assert rows["app.py"] == ("ok", "partial", "")
    assert rows["new.py"] == ("refuse", "untracked", "content:private-key")


def test_allow_overrides_one_path(repo: Path) -> None:
    """A path named with --allow is staged-safe; others stay refused."""
    (repo / ".env.test").write_text("A=1\n")
    (repo / ".env").write_text("A=1\n")
    _git(repo, "add", ".env.test")
    code, rows = _scan(repo, "--allow", ".env.test")
    assert code == 0
    assert rows[".env.test"][0] == "ok"
    assert rows[".env"][0] == "refuse"
