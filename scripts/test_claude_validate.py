"""Owned-fixture tests for the concurrent ``claude plugin validate`` runner."""

# ruff: noqa: S101, INP001, SLF001
import asyncio
import stat
import typing as t

import marketplace
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path

_FAKE = """\
#!/bin/sh
case "$4" in
  *bad*) printf '\\342\\235\\257 broken %s\\n' "$4"; exit 1 ;;
  *warn*) printf '\\342\\235\\257 careful\\n'; exit 0 ;;
  *slow*) sleep 5 ;;
esac
exit 0
"""


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put an executable ``claude`` stand-in first on ``PATH``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    _ = exe.write_text(_FAKE, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    return tmp_path


def test_results_keep_input_order(fake_claude: Path) -> None:
    """Findings come back per path in the order given, whatever finishes first."""
    paths = [fake_claude / "ok", fake_claude / "warn", fake_claude / "bad"]
    results = asyncio.run(marketplace._validate_all(paths))
    assert results == [
        ([], []),
        ([], ["claude validate: careful"]),
        ([f"claude validate: broken {fake_claude / 'bad'}"], []),
    ]


def test_timeout_reports_one_error(fake_claude: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung validation is killed and reported by directory name."""
    monkeypatch.setattr(marketplace, "VALIDATE_TIMEOUT_S", 0.2)
    gate = asyncio.Semaphore(1)
    result = asyncio.run(marketplace._run_claude_validate(fake_claude / "slow", gate))
    assert result == (["claude validate: slow timed out after 0.2s"], [])


def test_missing_cli_is_a_silent_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``claude`` on PATH a validation yields nothing."""
    monkeypatch.setenv("PATH", str(tmp_path))
    gate = asyncio.Semaphore(1)
    coro: t.Coroutine[t.Any, t.Any, tuple[list[str], list[str]]] = marketplace._run_claude_validate(
        tmp_path, gate
    )
    assert asyncio.run(coro) == ([], [])
