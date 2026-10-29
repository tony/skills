"""Exercise the preservation and executable-example assertions with broken artifacts."""

from __future__ import annotations

import hashlib
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from . import fixtures
from .checks import (
    _bind_record,  # pyright: ignore[reportPrivateUsage]
    _example,  # pyright: ignore[reportPrivateUsage]
    _workspace,  # pyright: ignore[reportPrivateUsage]
    check_report,
    verify,
)
from .fixtures import scaffold


def _case(tmp_path: Path, name: str) -> tuple[Path, dict[str, str]]:
    root = tmp_path / name
    root.mkdir()
    record = scaffold(name, root)
    record.unlink()
    project = root / "project"
    hashes = {
        p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in project.rglob("*")
        if p.is_file()
    }
    return root, hashes


def test_real_command_and_input_preservation(tmp_path: Path) -> None:
    """The example must run, while modifying its input fails the check."""
    root, hashes = _case(tmp_path, "new-cli")
    _ = (root / "outputs/README.md").write_text(
        "```console\n$ python3 tallylines.py sample.txt\n```\n"
    )
    verify(root, "new-cli", hashes)
    _ = (root / "outputs/README.md").write_text(
        """```console
$ python3 tallylines.py missing.txt
```
```console
$ python3 tallylines.py sample.txt
```
"""
    )
    with pytest.raises(ValueError, match="Runnable example"):
        verify(root, "new-cli", hashes)
    _ = (root / "project/sample.txt").write_text("changed\n")
    with pytest.raises(ValueError, match="Input changed"):
        verify(root, "new-cli", hashes)


def test_missing_artifact_is_not_success(tmp_path: Path) -> None:
    """A completed agent with no handoff is incomplete."""
    root, hashes = _case(tmp_path, "audit-only")
    with pytest.raises(ValueError, match="Missing assessment"):
        verify(root, "audit-only", hashes)


def test_existing_incoming_anchor_survives(tmp_path: Path) -> None:
    """Renaming a useful heading breaks its incoming route."""
    root, hashes = _case(tmp_path, "preserve-library")
    original = (root / "project/README.md").read_text()
    target = root / "outputs/README.md"
    _ = target.write_text(original)
    verify(root, "preserve-library", hashes)
    _ = target.write_text(original.replace("## Usage", "## Example"))
    with pytest.raises(ValueError, match="anchors"):
        verify(root, "preserve-library", hashes)


@pytest.mark.parametrize("broken", ["owner", "license"])
def test_generated_owner_and_license_contract(tmp_path: Path, broken: str) -> None:
    """A matching README alone cannot hide a lost owner or altered license."""
    root, hashes = _case(tmp_path, "generated-font")
    output = root / "outputs/project"
    _ = shutil.copytree(root / "project", output)
    verify(root, "generated-font", hashes)
    target = output / ("docs/README.template.md" if broken == "owner" else "docs/font-license.md")
    _ = target.write_text("different\n")
    with pytest.raises(ValueError, match=r"Generated README|License changed"):
        verify(root, "generated-font", hashes)


def test_hidden_fixture_is_not_standalone(tmp_path: Path) -> None:
    """The first snippet must supply its own setup."""
    root, hashes = _case(tmp_path, "example-contracts")
    target = root / "outputs/README.md"
    _ = target.write_text((root / "project/README.md").read_text())
    with pytest.raises(subprocess.CalledProcessError):
        verify(root, "example-contracts", hashes)
    _ = target.write_text(
        """```python
from toybridge import temporary_server

with temporary_server() as server:
    print(server.select_layout("classic"))
```
"""
    )
    verify(root, "example-contracts", hashes)


def test_unrelated_example_code_is_not_executed(tmp_path: Path) -> None:
    """Only fixture API calls may run in this deterministic check."""
    root, hashes = _case(tmp_path, "example-contracts")
    _ = (root / "outputs/README.md").write_text("```python\nimport os\nprint(os.getcwd())\n```\n")
    with pytest.raises(ValueError, match="imports outside"):
        verify(root, "example-contracts", hashes)


def test_empty_native_report_cannot_pass(tmp_path: Path) -> None:
    """A selected subset cannot stand in for the complete native suite."""
    result = check_report({"cases": []}, tmp_path)
    assert result["status"] == "UNVERIFIED"  # noqa: S101 -- Empty evidence must fail closed.


def test_baseline_workspace_cannot_certify_skill_arm(tmp_path: Path) -> None:
    """Similar path prefixes do not make two arms the same workspace."""
    skill = tmp_path / "trial"
    baseline = tmp_path / "trial-baseline"
    run: dict[str, object] = {"tracePath": str(skill / "out/trace.jsonl")}
    records: list[dict[str, object]] = [{"case": "example", "root": str(baseline / "work")}]
    with pytest.raises(ValueError, match="unique scaffold evidence"):
        _ = _bind_record("example", run, records)


def test_sealed_workspace_permissions_are_restored(tmp_path: Path) -> None:
    """Artifact inspection preserves the native runner's quarantine."""
    trial = tmp_path / "trial"
    recorded = trial / "home/cwd"
    recorded.mkdir(parents=True)
    _ = (recorded / "result.txt").write_text("fixture data")
    sealed = trial / "sealed"
    sealed.mkdir()
    _ = (trial / "home").rename(sealed / "home")
    sealed.chmod(0)
    try:
        with _workspace(recorded, trial / "out/trace.jsonl") as workspace:
            assert (workspace / "result.txt").read_text() == "fixture data"  # noqa: S101
        assert stat.S_IMODE(sealed.stat().st_mode) == 0  # noqa: S101
    finally:
        sealed.chmod(0o700)


def test_retained_workspace_code_is_not_loaded(tmp_path: Path) -> None:
    """Runtime checks use the verified source, never an actor's import path."""
    root, hashes = _case(tmp_path, "new-cli")
    _ = (root / "outputs/README.md").write_text(
        "```console\n$ python3 tallylines.py sample.txt\n```\n"
    )
    _ = (root / "project/argparse.py").write_text('raise RuntimeError("actor import executed")\n')
    verify(root, "new-cli", hashes)


@pytest.mark.parametrize("fence", ["text", "sh"])
def test_schematic_usage_is_distinct_from_first_use(tmp_path: Path, fence: str) -> None:
    """A usage synopsis does not invalidate a runnable sample command."""
    root, hashes = _case(tmp_path, "new-cli")
    _ = (root / "outputs/README.md").write_text(
        """```console
$ python3 tallylines.py sample.txt
```

## Usage

```FENCE
python3 tallylines.py FILE
```
""".replace("FENCE", fence)
    )
    verify(root, "new-cli", hashes)


@pytest.mark.parametrize("arguments", ["missing.txt", "--recursive sample.txt"])
def test_later_runnable_command_is_still_checked(tmp_path: Path, arguments: str) -> None:
    """One valid sample cannot hide another broken runnable instruction."""
    root, hashes = _case(tmp_path, "new-cli")
    _ = (root / "outputs/README.md").write_text(
        f"""```console
$ python3 tallylines.py sample.txt
```

## Usage

```console
$ python3 tallylines.py {arguments}
```
"""
    )
    with pytest.raises(ValueError, match="Runnable example"):
        verify(root, "new-cli", hashes)


def test_scaffold_excludes_unowned_bytecode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prior local import must not become an actor's prerequisite."""
    source = tmp_path / "suite/fixtures/synthetic"
    source.mkdir(parents=True)
    _ = (source / "README.md").write_text("Owned input\n")
    (source / "__pycache__").mkdir()
    _ = (source / "__pycache__/module.pyc").write_bytes(b"unowned")
    _ = (source / "module.pyc").write_bytes(b"unowned")
    monkeypatch.setattr(fixtures, "__file__", str(tmp_path / "suite/checks/fixtures.py"))
    record = scaffold("synthetic", tmp_path / "run")
    assert sorted(p.name for p in (tmp_path / "run/project").iterdir()) == ["README.md"]  # noqa: S101
    assert "__pycache__" not in record.read_text()  # noqa: S101


def test_example_execution_does_not_write_bytecode(tmp_path: Path) -> None:
    """Verification must leave its own source fixture unchanged."""
    source = tmp_path / "fixture"
    source.mkdir()
    original = Path(fixtures.__file__).parents[1] / "fixtures/example-contracts/toybridge.py"
    _ = shutil.copyfile(original, source / "toybridge.py")
    _example(
        source,
        """```python
from toybridge import temporary_server
with temporary_server() as server:
    print(server.select_layout('classic'))
```
""",
    )
    assert not (source / "__pycache__").exists()  # noqa: S101
