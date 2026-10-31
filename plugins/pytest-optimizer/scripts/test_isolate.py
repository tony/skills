"""Owned-Git proofs that execution never touches the user's checkout."""

# ruff: noqa: S101, S603, S607, INP001
import hashlib
import json
import pathlib
import shutil
import subprocess
import typing as t

import isolate
import pytest

pytestmark = pytest.mark.integration

ENV = (
    "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
)  # fmt: skip


def git(cwd: pathlib.Path, *args: str, check: bool = True) -> str:
    """Run git in ``cwd`` and return stdout."""
    proc = subprocess.run(
        ["git", *ENV, "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not check or proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a repository with two test files, a README and a side branch."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    (root / "tests" / "conftest.py").write_text("SCOPE = 'function'\n")
    (root / "tests" / "test_a.py").write_text("DELAY = 0.8\n")
    (root / "README.md").write_text("readme\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "branch", "side")
    return root


def make_patch(repo: pathlib.Path, out: pathlib.Path, path: str, text: str) -> dict[str, t.Any]:
    """Record a candidate the way 01-benchmark does, in a detached scratch tree."""
    started = isolate.start(repo, "HEAD")
    assert started["ok"], started
    tree = pathlib.Path(started["tree"])
    (tree / path).write_text(text)
    captured = isolate.capture(tree, out)
    assert captured["ok"], captured
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    return captured


def snapshot(repo: pathlib.Path) -> dict[str, t.Any]:
    """Everything the user could lose: refs, index, status and file bytes."""
    files = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(repo).parts
    }
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "symbolic-ref", "HEAD"),
        "refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"),
        "index": (repo / ".git" / "index").read_bytes(),
        "status": git(repo, "status", "--porcelain=v2", "--untracked-files=all"),
        "files": files,
    }


def test_failed_item_and_user_edits_never_cross_the_boundary(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """A good item, concurrent user edits and a failing item leave the checkout alone."""
    good = make_patch(repo, tmp_path / "good.patch", "tests/conftest.py", "SCOPE = 'session'\n")
    bad = make_patch(repo, tmp_path / "bad.patch", "tests/test_a.py", "DELAY = 0.0\n")
    base = git(repo, "rev-parse", "HEAD")
    before_refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads").split("\n")

    started = isolate.start(repo, base, "pytest-optimizer/run1")
    assert started["ok"], started
    tree = pathlib.Path(started["tree"])

    applied = isolate.apply(tree, tmp_path / "good.patch", good["sha256"], ["tests/conftest.py"])
    assert applied["ok"], applied
    gated = isolate.gate(tree, ["tests/conftest.py"])
    assert gated["ok"], gated
    git(tree, "commit", "-q", "-m", "item one")
    assert isolate.landed(tree, gated["parent"], gated["tree"])["ok"]

    # The user keeps working while the run is in flight.
    (repo / "README.md").write_text("readme, edited by the user\n")
    (repo / "notes.txt").write_text("untracked user notes\n")
    (repo / "tests" / "test_a.py").write_text("DELAY = 0.8  # user edit\n")
    git(repo, "add", "tests/test_a.py")
    (repo / ".git" / "index.lock").write_text("")
    midway = snapshot(repo)

    applied = isolate.apply(tree, tmp_path / "bad.patch", bad["sha256"], ["tests/test_a.py"])
    assert applied["ok"], applied
    assert (tree / "tests" / "test_a.py").read_text() == "DELAY = 0.0\n"
    assert isolate.reset(tree)["ok"]
    assert (tree / "tests" / "test_a.py").read_text() == "DELAY = 0.8\n"
    assert git(tree, "status", "--porcelain") == ""
    assert git(tree, "rev-list", "--count", f"{base}..HEAD") == "1"

    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert snapshot(repo) == midway

    (repo / ".git" / "index.lock").unlink()
    after_refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads").split("\n")
    assert sorted(after_refs) == sorted([*before_refs, "refs/heads/pytest-optimizer/run1"])
    git(repo, "merge", "--ff-only", "pytest-optimizer/run1")
    assert (repo / "tests" / "conftest.py").read_text() == "SCOPE = 'session'\n"
    assert (repo / "README.md").read_text() == "readme, edited by the user\n"
    assert (repo / "notes.txt").read_text() == "untracked user notes\n"


def test_reset_and_apply_refuse_the_users_checkout(repo: pathlib.Path) -> None:
    """Only a worktree this tool created can be reset or patched."""
    (repo / "README.md").write_text("dirty\n")
    (repo / "scratch.txt").write_text("untracked\n")

    for refusal in (isolate.reset(repo), isolate.gate(repo, ["README.md"])):
        assert refusal["ok"] is False
    assert (repo / "README.md").read_text() == "dirty\n"
    assert (repo / "scratch.txt").exists()
    assert isolate.finish(repo)["removed"] is False
    assert repo.exists()


def test_apply_rejects_altered_patch_and_wrong_file_set(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """A patch whose bytes or paths differ from the plan is never applied."""
    patch = tmp_path / "p.patch"
    cap = make_patch(repo, patch, "tests/conftest.py", "SCOPE = 'session'\n")
    started = isolate.start(repo, "HEAD")
    tree = pathlib.Path(started["tree"])

    assert isolate.apply(tree, patch, "0" * 64, ["tests/conftest.py"])["ok"] is False
    wrong = isolate.apply(tree, patch, cap["sha256"], ["tests/test_a.py"])
    assert wrong["ok"] is False
    assert git(tree, "status", "--porcelain") == ""
    patch.write_bytes(patch.read_bytes() + b"\n")
    assert isolate.apply(tree, patch, cap["sha256"], ["tests/conftest.py"])["ok"] is False
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_gate_and_landed_catch_extra_paths_and_hook_edits(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Files the run created, and bytes a hook changed, never pass as the gated item."""
    patch = tmp_path / "p.patch"
    cap = make_patch(repo, patch, "tests/conftest.py", "SCOPE = 'session'\n")
    started = isolate.start(repo, "HEAD", "pytest-optimizer/run2")
    tree = pathlib.Path(started["tree"])
    assert isolate.apply(tree, patch, cap["sha256"], ["tests/conftest.py"])["ok"]

    (tree / "stray.log").write_text("written by a timed test\n")
    stray = isolate.gate(tree, ["tests/conftest.py"])
    assert (stray["ok"], stray["paths"]) == (False, ["stray.log"])
    (tree / "stray.log").unlink()

    gated = isolate.gate(tree, ["tests/conftest.py"])
    assert gated["ok"]
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho '# hooked' >> tests/conftest.py\ngit add tests/conftest.py\n")
    hook.chmod(0o755)
    git(tree, "commit", "-q", "-m", "item")
    result = isolate.landed(tree, gated["parent"], gated["tree"])
    assert (result["ok"], result["reason"]) == (False, "committed tree differs from the gated tree")
    assert isolate.reset(tree, gated["parent"])["ok"]
    assert git(tree, "rev-parse", "HEAD") == gated["parent"]
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_finish_removes_only_its_own_worktree(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Another worktree on the repository survives; no prune is involved."""
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "--detach", str(other))
    started = isolate.start(repo, "HEAD")

    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert other.is_dir()
    assert str(other.resolve()) in git(repo, "worktree", "list", "--porcelain")
    assert started["dir"] not in git(repo, "worktree", "list", "--porcelain")


def test_finish_drops_only_an_unused_result_branch(repo: pathlib.Path) -> None:
    """A branch with commits is kept; an untouched one is removed."""
    base = git(repo, "rev-parse", "HEAD")
    kept = isolate.start(repo, base, "pytest-optimizer/kept")
    kept_tree = pathlib.Path(kept["tree"])
    (kept_tree / "new.txt").write_text("x\n")
    git(kept_tree, "add", "new.txt")
    git(kept_tree, "commit", "-q", "-m", "work")
    unused = isolate.start(repo, base, "pytest-optimizer/unused")

    assert isolate.finish(pathlib.Path(kept["dir"]), base)["branch_dropped"] is False
    assert isolate.finish(pathlib.Path(unused["dir"]), base)["branch_dropped"] is True
    branches = git(repo, "branch", "--list", "pytest-optimizer/*")
    assert "kept" in branches
    assert "unused" not in branches


def test_export_fallback_captures_a_bound_patch(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A host that refuses worktrees still yields the same hash-bound patch."""
    (repo / "untracked.txt").write_text("not exported\n")
    started = isolate.start(repo, "HEAD", export=True)
    tree = pathlib.Path(started["tree"])
    assert not (tree / "untracked.txt").exists()
    (tree / "tests" / "conftest.py").write_text("SCOPE = 'session'\n")
    cap = isolate.capture(tree, tmp_path / "e.patch")

    assert cap["ok"]
    assert cap["sha256"] == hashlib.sha256((tmp_path / "e.patch").read_bytes()).hexdigest()
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert "untracked.txt" in git(repo, "status", "--porcelain")


def test_inputs_digest_binds_dirty_and_untracked_bytes(repo: pathlib.Path) -> None:
    """Edits that keep HEAD and node ids unchanged still change the digest."""
    clean = isolate.inputs(repo)
    assert clean["dirty"] is False

    (repo / "tests" / "test_a.py").write_text("DELAY = 0.1\n")
    tracked = isolate.inputs(repo)
    (repo / "helper.py").write_text("X = 1\n")
    untracked = isolate.inputs(repo)
    (repo / "helper.py").write_text("X = 2\n")

    digests = [
        clean["digest"],
        tracked["digest"],
        untracked["digest"],
        isolate.inputs(repo)["digest"],
    ]
    assert len(set(digests)) == len(digests)
    assert (tracked["dirty"], untracked["untracked"]) == (True, 1)


def test_inputs_digest_covers_the_whole_repo_from_a_subdirectory(repo: pathlib.Path) -> None:
    """A monorepo project directory still binds untracked bytes anywhere in the repo."""
    sub = repo / "pkg"
    sub.mkdir()
    (sub / "m.py").write_text("X = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pkg")
    (repo / "top.txt").write_text("a\n")
    (sub / "new.py").write_text("Y = 1\n")
    before = isolate.inputs(sub)

    (repo / "top.txt").write_text("b\n")
    root_edit = isolate.inputs(sub)
    (sub / "new.py").write_text("Y = 2\n")
    sub_edit = isolate.inputs(sub)

    digests = {before["digest"], root_edit["digest"], sub_edit["digest"]}
    assert (before["untracked"], len(digests)) == (2, 3)
    assert sub_edit["digest"] == isolate.inputs(repo)["digest"]


def test_start_reports_the_project_directory_inside_the_tree(repo: pathlib.Path) -> None:
    """A run started from a subdirectory gets a workdir at the same relative path."""
    (repo / "pkg").mkdir()
    (repo / "pkg" / "m.py").write_text("X = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pkg")
    started = isolate.start(repo / "pkg", "HEAD")

    assert started["workdir"] == str(pathlib.Path(started["tree"]) / "pkg")
    assert (pathlib.Path(started["workdir"]) / "m.py").is_file()
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_export_keeps_files_marked_export_ignore(repo: pathlib.Path) -> None:
    """The fallback tree holds every committed file, including the tests."""
    (repo / ".gitattributes").write_text("tests export-ignore\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "attrs")
    started = isolate.start(repo, "HEAD", export=True)
    tree = pathlib.Path(started["tree"])

    assert (tree / "tests" / "test_a.py").read_text() == "DELAY = 0.8\n"
    assert git(tree, "status", "--porcelain") == ""
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_resume_reopens_a_branch_whose_scratch_directory_is_gone(repo: pathlib.Path) -> None:
    """A cleaned temp directory leaves a stale worktree record that must not block resume."""
    first = isolate.start(repo, "HEAD", "pytest-optimizer/run3")
    shutil.rmtree(first["dir"])

    again = isolate.start(repo, "HEAD", "pytest-optimizer/run3", existing=True)

    assert again["ok"], again
    assert isolate.owner_of(pathlib.Path(again["tree"]))[0] is not None
    assert isolate.finish(pathlib.Path(again["dir"]))["removed"]


def test_stale_names_the_first_check_that_fails(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Each broken binding is reported alone, with the phase that repairs it."""
    memory = tmp_path / "memory"
    memory.mkdir()
    head = git(repo, "rev-parse", "HEAD")
    digest = isolate.inputs(repo)["digest"]
    state = {
        "env_token": "tok",
        "dirty": False,
        "base_head": head,
        "inputs_digest": digest,
        "completed": {"plan": True},
    }
    (memory / "baseline.json").write_text(
        json.dumps({"test_command": "pytest", "pytest_version": "9.1.1"})
    )

    def check(phase: str = "benchmark", **kw: str) -> dict[str, t.Any]:
        (memory / "state.json").write_text(json.dumps(state))
        return isolate.stale(memory, repo, phase, **kw)

    assert check(command="pytest", pytest_version="9.1.1")["ok"]
    assert check(command="tox")["reason"] == "the test command differs from the scan's"
    assert check(pytest_version="8.0")["reason"] == "the pytest version differs from the scan's"
    (repo / "extra.py").write_text("X = 1\n")
    assert check()["reason"] == "the working tree differs from the scan's"
    (repo / "extra.py").unlink()
    state["dirty"] = True
    assert check()["reason"] == "the scan ran on a dirty tree"
    state.update(dirty=False, base_head="0" * 40)
    assert check()["reason"] == "HEAD differs from the scan's commit"
    state["base_head"] = head
    (memory / "benchmarks.json").write_text(
        json.dumps([{"id": "a", "verdict": "validated", "env_token": "old", "base_head": head}])
    )
    assert check("plan")["reason"] == "a has a different token"
    (memory / "benchmarks.json").write_text(
        json.dumps([{"id": "a", "verdict": "validated", "env_token": "tok", "base_head": head}])
    )
    assert check("plan")["reason"] == "a has no patch hash"


def test_stale_execute_binds_the_approved_plan(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A plan edited after approval is refused before any worktree opens."""
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"id": "a", "env_token": "tok", "patch_sha256": "x"}]))
    state = {
        "env_token": "tok",
        "dirty": False,
        "base_head": git(repo, "rev-parse", "HEAD"),
        "completed": {"plan": True},
        "plan_hash": hashlib.sha256(plan.read_bytes()).hexdigest(),
    }
    (tmp_path / "state.json").write_text(json.dumps(state))
    assert isolate.stale(tmp_path, repo, "execute")["ok"]

    plan.write_text(plan.read_text() + " ")
    result = isolate.stale(tmp_path, repo, "execute")
    assert (result["reason"], result["rerun"]) == ("the plan changed after approval", "02-plan")
    (tmp_path / "state.json").write_text(json.dumps({**state, "env_token": None}))
    assert isolate.stale(tmp_path, repo, "execute")["reason"] == "the plan changed after approval"


def test_main_exits_nonzero_with_a_reason_on_refusal(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A refused command exits 1 and prints one JSON reason."""
    assert isolate.main(["reset", "--cwd", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["reason"]
    assert isolate.main(["stale", "--memory-dir", str(tmp_path), "--phase", "plan"]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "state.json is missing or unreadable"


def test_resume_leaves_a_users_prunable_worktree_alone(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Only this run's lost record is dropped; a moved user worktree stays listed."""
    mine = isolate.start(repo, "HEAD", "pytest-optimizer/run4")
    users = tmp_path / "users"
    git(repo, "worktree", "add", "-q", "--detach", str(users))
    users.rename(tmp_path / "users-moved")
    shutil.rmtree(mine["dir"])

    again = isolate.start(repo, "HEAD", "pytest-optimizer/run4", existing=True)

    assert again["ok"], again
    listing = git(repo, "worktree", "list", "--porcelain")
    assert str(users) in listing
    assert isolate.finish(pathlib.Path(again["dir"]))["removed"]


def test_start_refuses_a_repository_that_is_or_contains_home(
    repo: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scratch copy of the home directory is refused before anything is created."""
    for home in (repo, repo / "tests"):
        monkeypatch.setenv("HOME", str(home))
        result = isolate.start(repo, "HEAD")
        assert result["ok"] is False
        assert "home directory" in result["reason"]
    monkeypatch.setenv("HOME", str(repo.parent))
    started = isolate.start(repo, "HEAD")
    assert started["ok"], started
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_exists_lists_missing_paths_and_honors_created_files(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A planned file must be at HEAD unless the patch creates it."""
    started = isolate.start(repo, "HEAD")
    tree = pathlib.Path(started["tree"])
    (tree / "tests" / "new.py").write_text("X = 1\n")
    cap = isolate.capture(tree, tmp_path / "n.patch")
    assert cap["ok"]
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    files = ["tests/test_a.py", "tests/new.py", "tests/gone.py"]

    assert isolate.exists(repo, files)["missing"] == ["tests/new.py", "tests/gone.py"]
    assert isolate.exists(repo, files, tmp_path / "n.patch")["missing"] == ["tests/gone.py"]
    argv = ["exists", "--cwd", str(repo), "--file", "tests/gone.py"]
    assert isolate.main(argv) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "absent at HEAD"
