"""Real-pytest checks for the opt-in scaffolds."""

# ruff: noqa: S101, S603, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false, reportImplicitStringConcatenation=false
import os
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "templates"


def run_pytest(project: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run pytest in ``project`` with the templates importable."""
    env = {**os.environ, "PYTHONPATH": str(TEMPLATES), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_timing_plugin_separates_overridden_fixtures_and_resets_between_sessions(
    tmp_path: pathlib.Path,
) -> None:
    """Same-named fixtures get separate rows; a second in-process session starts empty."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "conftest.py").write_text(
        "import pytest\n"
        "pytest_plugins = ['pytest_optimizer_plugin']\n"
        "@pytest.fixture\n"
        "def res():\n    return 1\n"
        "@pytest.fixture(scope='session', params=[1, 2])\n"
        "def shared(request):\n    return request.param\n",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "conftest.py").write_text(
        "import pytest\n@pytest.fixture\ndef res():\n    return 2\n",
    )
    (tmp_path / "test_top.py").write_text("def test_a(res, shared):\n    assert res\n")
    (sub / "test_sub.py").write_text("def test_b(res):\n    assert res\n")

    proc = run_pytest(tmp_path)

    assert proc.returncode == 0, proc.stdout
    rows = [ln for ln in proc.stdout.splitlines() if ln.rstrip().endswith(")") and " res (" in ln]
    assert len(rows) > 1
    shared = next(ln for ln in proc.stdout.splitlines() if " shared (" in ln)
    assert shared.split()[1] == "2"

    twice = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pytest; pytest.main(['-q']); pytest.main(['-q'])",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(TEMPLATES), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    counts = [ln.split()[1] for ln in twice.stdout.splitlines() if " shared (" in ln]
    assert counts == ["2", "2"]


def test_cache_snippet_serves_the_second_run_and_refuses_empty_inputs(
    tmp_path: pathlib.Path,
) -> None:
    """The memoized artifact is built once across runs and never without inputs."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "input.txt").write_text("v1\n")
    snippet = (TEMPLATES / "conftest_cache_snippet.py").read_text()
    snippet = snippet.replace(
        "INPUTS: tuple[pathlib.Path, ...] = ()",
        "INPUTS = (pathlib.Path(__file__).parent / 'input.txt',)",
    ).replace(
        "    raise NotImplementedError",
        "    (pathlib.Path(__file__).parent / 'built.log').open('a').write('x')\n"
        "    return {'n': 1}",
    )
    (tmp_path / "conftest.py").write_text(snippet)
    (tmp_path / "test_x.py").write_text(
        "def test_x(expensive_artifact):\n    assert expensive_artifact\n"
    )

    assert run_pytest(tmp_path).returncode == 0
    assert run_pytest(tmp_path).returncode == 0
    assert (tmp_path / "built.log").read_text() == "x"

    (tmp_path / "input.txt").write_text("v2\n")
    assert run_pytest(tmp_path).returncode == 0
    assert (tmp_path / "built.log").read_text() == "xx"

    (tmp_path / "conftest.py").write_text(snippet.replace("INPUTS = (", "INPUTS = () and ("))
    assert "set INPUTS" in run_pytest(tmp_path).stdout
