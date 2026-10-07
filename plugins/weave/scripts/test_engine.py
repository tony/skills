"""Integration tests for engine.py: real git repositories, stub model CLIs on PATH."""

# ruff: noqa: S101, S603, INP001, PLR2004, D103, ARG001
# pyright: reportAny=false, reportUnusedParameter=false, reportUnusedCallResult=false
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import engine  # pyright: ignore[reportImplicitRelativeImport]
import pytest


def sh(cwd: Path, *argv: str) -> str:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "work" / "Demo Repo"
    root.mkdir(parents=True)
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.com")
    sh(root, "git", "config", "user.name", "t")
    (root / "sub").mkdir()
    for name, text in (("a.txt", "one\n"), ("B", "b1\n"), ("C", "c1\n"), ("sub/S", "s1\n")):
        (root / name).write_text(text)
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", "init")
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.setenv("WEAVE_REPO", str(root))
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def bindir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "bin"
    path.mkdir()
    monkeypatch.setenv("PATH", f"{path}:/usr/bin:/bin")
    return path


def stub(bindir: Path, name: str, body: str) -> None:
    script = bindir / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)


def init(
    command: str = "ask",
    backend: str = "subagents",
    *,
    mutating: bool = False,
    variants: int | None = None,
) -> engine.Json:
    return engine.init_session(
        command=command,
        backend=backend,
        repo=".",
        prompt_summary="q" * 200,
        passes=1,
        timeout="default",
        mutating=mutating,
        variants=variants,
    )


def prompt_file(session: engine.Json) -> Path:
    path = Path(session["session_dir"]) / "prompt.md"
    path.write_text("Question?")
    return path


def read_only_session(backend: str = "model-clis") -> tuple[Path, engine.Json]:
    doc = init(backend=backend)
    return Path(doc["session_dir"]), doc


def dispatch(sdir: Path, lane: str, **kw: object) -> engine.Json:
    kw.setdefault("timeout", 5)
    kw.setdefault("mutating", False)
    kw.setdefault("rate_wait", 0)
    return engine.dispatch_lane(
        sdir,
        lane,
        n=1,
        prompt_file=prompt_file({"session_dir": str(sdir)}),
        **kw,  # pyright: ignore[reportArgumentType]
    )


def user_state(repo: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for p in sorted(repo.rglob("*")):
        if ".git" in p.relative_to(repo).parts or not p.is_file():
            continue
        state[str(p.relative_to(repo))] = p.read_text()
    return state


# --- session setup ---------------------------------------------------------


def test_init_writes_session_files(repo: Path) -> None:
    doc = init()
    sdir = Path(doc["session_dir"])
    session = json.loads((sdir / "session.json").read_text())
    assert session["participants"] == ["maintainer", "skeptic", "builder"]
    assert session["executors"]["skeptic"] == "host-native"
    assert session["worker_backend"] == "subagents"
    assert "models" not in session
    assert len(session["prompt_summary"]) == 120
    assert (sdir / "pass-0001" / "outputs").is_dir()
    assert not (sdir / "pass-0001" / "diffs").exists()
    assert (sdir / "metadata.md").is_file()
    event = json.loads((sdir / "events.jsonl").read_text().splitlines()[0])
    assert event["event"] == "session_start"
    assert event["worker_backend"] == "subagents"
    assert event["participants"] == ["maintainer", "skeptic", "builder"]
    assert (sdir.parents[2] / "repo.json").is_file()
    assert doc["trunk"] == "main"
    assert len(doc["baseline_sha"]) == 40
    assert doc["repo_dir"].startswith("demo-repo--")


def test_init_variants_lists_artifacts(repo: Path) -> None:
    doc = init(command="brainstorm", variants=2)
    assert doc["artifacts"][:3] == ["maintainer-v1", "maintainer-v2", "skeptic-v1"]
    assert (Path(doc["session_dir"]) / "outputs").is_dir()


def test_init_model_clis_roster_follows_installed_clis(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    stub(bindir, "agent", "exit 0")
    doc = init(backend="model-clis")
    assert doc["participants"] == ["claude", "agy", "gpt"]
    assert doc["executors"] == {"claude": "host", "agy": "agent", "gpt": "codex"}
    session = json.loads((Path(doc["session_dir"]) / "session.json").read_text())
    assert "agy: gemini-3.1-pro" in session["models"]


def test_update_drops_participant_and_links_latest(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    sdir = Path(init(backend="model-clis")["session_dir"])
    engine.update_session(
        sdir, status="completed", completed_passes=1, event="session_complete",
        event_json='{"x": 1}', drop=["claude"], sets=[], link_latest=True,
    )  # fmt: skip
    session = engine.load_session(sdir)
    assert session["status"] == "completed"
    assert session["participants"] == ["gpt"]
    assert "claude" not in session["executors"]
    assert (sdir.parent / "latest").resolve() == sdir.resolve()
    last = json.loads((sdir / "events.jsonl").read_text().splitlines()[-1])
    assert last["event"] == "session_complete"
    assert last["x"] == 1


def test_detect_reports_clis_and_search_tools(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    doc = engine.detect()
    assert doc["clis"] == {"agy": False, "codex": True, "agent": False}
    assert doc["lanes"]["agy"] is None
    assert doc["lanes"]["gpt"]["executor"] == "codex"
    assert doc["search"]["files"] in ("fd", "find")


# --- repo guard ------------------------------------------------------------

DIRTY_A = "one\nUSER-DIRTY-A\n"


def guarded_session(repo: Path) -> Path:
    (repo / "a.txt").write_text(DIRTY_A)
    (repo / "U").write_text("user untracked\n")
    return Path(init(backend="model-clis")["session_dir"])


def cli_writes(repo: Path) -> None:
    (repo / "B").write_text("b1\nCLI-B\n")
    (repo / "N").write_text("cli new\n")
    (repo / "newdir").mkdir()
    (repo / "newdir" / "M").write_text("x\n")
    with (repo / "a.txt").open("a") as fh:
        fh.write("CLI-A\n")


def test_guard_pin_and_index_untouched(repo: Path) -> None:
    (repo / "a.txt").write_text(DIRTY_A)
    sh(repo, "git", "add", "a.txt")
    index_before = (repo / ".git" / "index").read_bytes()
    sdir = Path(init(backend="model-clis")["session_dir"])
    session = engine.load_session(sdir)
    ref = f"refs/weave-guard/{session['session_id']}/pre"
    assert sh(repo, "git", "rev-parse", ref).strip() == session["guard"]["pre"]
    assert sh(repo, "git", "show", f"{ref}:a.txt") == DIRTY_A
    assert engine.guard_check(sdir)["violation"] is False
    assert (repo / ".git" / "index").read_bytes() == index_before


def test_guard_detects_further_edit_of_dirty_file_and_never_mutates(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    after = user_state(repo)
    found = engine.guard_check(sdir, "agy")
    assert found["violation"] is True
    assert found["touched"] == {"a.txt": "M", "B": "M", "N": "A", "newdir/M": "A"}
    assert "U" not in found["touched"]
    vdir = Path(found["dir"])
    assert "CLI-A" in (vdir / "violation.patch").read_text()
    assert (vdir / "post-copy" / "a.txt").read_text() == DIRTY_A + "CLI-A\n"
    post_ref = f"refs/weave-guard/{engine.load_session(sdir)['session_id']}/post-{found['id']}"
    assert sh(repo, "git", "rev-parse", "--verify", post_ref).strip()
    assert user_state(repo) == after
    events = (sdir / "guard-events.jsonl").read_text()
    assert '"repo_guard_violation"' in events
    assert '"reverted": false' in events
    assert engine.guard_check(sdir, "gpt").get("repeat") is True


def test_guard_and_capture_survive_non_utf8_files(repo: Path) -> None:
    latin1 = b"caf\xe9\n"
    sdir = guarded_session(repo)
    (repo / "latin.txt").write_bytes(latin1)
    found = engine.guard_check(sdir, "agy")
    assert found["violation"] is True
    assert (Path(found["dir"]) / "violation.patch").read_bytes().count(b"caf") >= 1
    assert (Path(found["dir"]) / "post-copy" / "latin.txt").read_bytes() == latin1
    engine.guard_resolve(sdir, "revert")
    assert not (repo / "latin.txt").exists()
    wdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(wdir, ["maintainer"])
    wt = Path(engine.load_session(wdir)["worktrees"]["maintainer"]["path"])
    (wt / "latin.txt").write_bytes(latin1)
    cap = engine.capture_tree(wdir, 1, "maintainer", None)
    assert cap["changed"] == ["latin.txt"]
    assert latin1 in Path(cap["patch"]).read_bytes()


def test_guard_clean_run_has_no_violation(repo: Path) -> None:
    sdir = guarded_session(repo)
    assert engine.guard_check(sdir)["violation"] is False
    assert engine.guard_resolve(sdir, "revert")["action"] == "none"


def test_guard_keep_changes_nothing(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    after = user_state(repo)
    assert engine.guard_resolve(sdir, "keep")["action"] == "keep"
    assert user_state(repo) == after


def test_guard_revert_restores_only_touched_paths(repo: Path) -> None:
    sdir = guarded_session(repo)
    pre_tree = engine.load_session(sdir)["guard"]["tree"]
    (repo / "sub" / "S").write_text("s1\n")
    cli_writes(repo)
    done = engine.guard_resolve(sdir, "revert")
    assert done["clean"] is True
    assert (repo / "a.txt").read_text() == DIRTY_A
    assert (repo / "B").read_text() == "b1\n"
    assert not (repo / "N").exists()
    assert not (repo / "newdir").exists()
    assert (repo / "U").read_text() == "user untracked\n"
    assert engine.snapshot_tree(repo) == pre_tree
    assert sh(repo, "git", "diff", "--cached", "--name-only") == ""


def test_guard_revert_keeps_concurrent_user_edit_recoverable(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    (repo / "C").write_text("c1\nUSER-C-EDIT\n")
    found = engine.guard_check(sdir, "agy")
    assert found["touched"]["C"] == "M"
    engine.guard_resolve(sdir, "revert")
    assert (repo / "C").read_text() == "c1\n"
    sid = engine.load_session(sdir)["session_id"]
    post = sh(repo, "git", "show", f"refs/weave-guard/{sid}/post-{found['id']}:C")
    assert "USER-C-EDIT" in post
    assert "USER-C-EDIT" in (Path(found["dir"]) / "post-copy" / "C").read_text()
    assert (repo / "a.txt").read_text() == DIRTY_A


def test_guard_quarantine_stashes_everything_by_name(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    (repo / "C").write_text("c1\nUSER-C-EDIT\n")
    done = engine.guard_resolve(sdir, "quarantine")
    assert sh(repo, "git", "status", "--porcelain") == ""
    assert "weave-guard-" in sh(repo, "git", "stash", "list")
    assert "USER-C-EDIT" in sh(repo, "git", "show", "stash@{0}:C")
    assert "USER-DIRTY-A" in sh(repo, "git", "show", "stash@{0}:a.txt")
    assert "user untracked" in sh(repo, "git", "show", "stash@{0}^3:U")
    pre = engine.load_session(sdir)["guard"]["pre"]
    assert sh(repo, "git", "show", f"{pre}:a.txt") == DIRTY_A
    assert done["stash"]["sha"]


def test_guard_head_move_is_reported_not_undone(repo: Path) -> None:
    sdir = guarded_session(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "escape")
    head = sh(repo, "git", "rev-parse", "HEAD")
    found = engine.guard_check(sdir)
    assert found["head_changed"] is True
    engine.guard_resolve(sdir, "revert")
    assert sh(repo, "git", "rev-parse", "HEAD") == head


def test_guard_finish_prunes_only_clean_sessions(repo: Path) -> None:
    sdir = guarded_session(repo)
    sid = engine.load_session(sdir)["session_id"]
    assert engine.guard_finish(sdir)["refs_pruned"] is True
    assert sh(repo, "git", "for-each-ref", f"refs/weave-guard/{sid}/") == ""
    dirty = guarded_session(repo)
    cli_writes(repo)
    done = engine.guard_finish(dirty)
    assert done["clean"] is False
    assert done["refs_pruned"] is False
    assert sh(repo, "git", "for-each-ref", "refs/weave-guard/")
    assert engine.guard_prune(".", 0.0)["dropped"]
    assert sh(repo, "git", "for-each-ref", "refs/weave-guard/") == ""


def test_dispatch_cli_sees_uncommitted_work_in_disposable_worktree(
    repo: Path, bindir: Path
) -> None:
    stub(bindir, "agy", 'cat a.txt U; echo "$PWD" >&2; echo scribble > scribble.txt')
    sdir = guarded_session(repo)
    doc = dispatch(sdir, "agy")
    assert doc["ok"], doc
    text = Path(doc["output"]).read_text()
    assert "USER-DIRTY-A" in text
    assert "user untracked" in text
    assert "agy-ro" in Path(doc["stderr"]).read_text()
    assert doc["guard_violations"] == []
    assert not (repo / "scribble.txt").exists()
    assert not list((sdir / "worktrees").glob("*"))
    assert len(sh(repo, "git", "worktree", "list").splitlines()) == 1


def test_dispatch_reports_an_escaped_write_without_reverting(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo escaped > "$WEAVE_REPO/escape.txt"; printf answer')
    sdir = guarded_session(repo)
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert len(doc["guard_violations"]) == 1
    assert (repo / "escape.txt").read_text() == "escaped\n"
    assert (repo / "a.txt").read_text() == DIRTY_A


# --- dispatch --------------------------------------------------------------


def test_dispatch_ok_composes_prompt(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'printf "%s" "$*" | grep -q read-only && printf "answer"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert Path(doc["output"]).read_text() == "answer"
    composed = (sdir / "pass-0001" / "prompts" / "gpt.md").read_text()
    assert composed.startswith("You are the Builder.")
    assert "READ-ONLY" in composed


def test_dispatch_variant_and_judge_paths(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'printf "%s" "$*"')
    sdir, _ = read_only_session()
    task = engine.lane_task(sdir, "gpt", n=1, variant=2, of=3)
    doc = dispatch(sdir, "gpt", task=task)
    assert doc["output"] == str(sdir / "outputs" / "gpt-v2.md")
    composed = (sdir / "pass-0001" / "prompts" / "gpt-v2.md").read_text()
    assert composed.startswith(engine.VARIANT_DIRECTIVE)
    assert "You are the Builder" not in composed
    judge = dispatch(sdir, "gpt", task=engine.lane_task(sdir, "gpt", n=1, judge=True))
    assert judge["output"] == str(sdir / "pass-0001" / "judges" / "gpt.md")
    assert not (sdir / "pass-0001" / "prompts" / "judge-gpt.md").read_text().startswith("You are")


def test_dispatch_credit_falls_back_to_agent_without_retry(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo "insufficient_quota" >&2; exit 1')
    stub(bindir, "agent", 'printf "from-agent"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert [a["class"] for a in doc["attempts"]] == ["credit", "ok"]
    assert doc["executor"] == "agent"
    assert doc["model"] == "gpt-5.4-high"


@pytest.mark.parametrize("text", engine.CREDIT_PATTERNS)
def test_every_credit_string_is_classified(text: str) -> None:
    got = engine.classify(returncode=1, timed_out=False, output_size=0, stderr=f"x {text} y")
    assert got == "credit"


def test_dispatch_rate_limit_retries_then_falls_back(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo "429 Too Many Requests" >&2; exit 1')
    stub(bindir, "agent", "exit 0")
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    classes = [a["class"] for a in doc["attempts"]]
    assert classes == ["rate-limit", "rate-limit", "empty", "empty", "empty", "empty"]
    assert doc["ok"] is False
    assert doc["failure_class"] == "empty"


def test_dispatch_crash_stops_lane(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "echo boom >&2; exit 3")
    stub(bindir, "agent", 'printf "never"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["failure_class"] == "crash"
    assert len(doc["attempts"]) == 1


def test_dispatch_timeout_grows_then_kills(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exec sleep 30")
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt", timeout=0.2)
    assert doc["failure_class"] == "timeout"
    assert "timeout=0.2" in Path(doc["stderr"]).read_text()
    assert "timeout=0.3" in Path(doc["stderr"]).read_text()


def test_lane_without_cli_is_unavailable(repo: Path, bindir: Path) -> None:
    sdir, _ = read_only_session()
    assert dispatch(sdir, "agy")["failure_class"] == "unavailable"


def test_argv_contract() -> None:
    wd = Path("/w")
    agy = engine.build_command("agy", "M", "P", mutating=False, workdir=wd)
    assert agy == ["agy", "--model", "M", "--add-dir", "/w", "--dangerously-skip-permissions",
                   "-p", "P"]  # fmt: skip
    codex = engine.build_command("codex", None, "P", mutating=False, workdir=wd)
    assert codex[:7] == ["codex", "exec", "-s", "read-only", "-C", "/w", "--skip-git-repo-check"]
    agent = engine.build_command("agent", "M", "P", mutating=False, workdir=wd)
    assert agent[:4] == ["agent", "-p", "--mode", "plan"]
    assert "-f" not in agent
    assert "--yolo" in engine.build_command("codex", None, "P", mutating=True, workdir=wd)


# --- mutating sessions -----------------------------------------------------


def test_mutating_lane_runs_in_registered_worktree(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo built > made.txt; printf "explained"')
    doc = init(command="execute", backend="model-clis", mutating=True)
    sdir = Path(doc["session_dir"])
    made = engine.create_worktrees(sdir, ["gpt"], "20000101-000000")
    wt = Path(made["worktrees"]["gpt"]["path"])
    assert made["worktrees"]["gpt"]["branch"] == "weave/gpt/20000101-000000"
    result = dispatch(sdir, "gpt", mutating=True)
    assert result["ok"], result
    assert (wt / "made.txt").exists()
    assert not (repo / "made.txt").exists()
    index = (wt / ".git").read_text()
    cap = engine.capture_tree(sdir, 1, "gpt", None)
    assert cap["changed"] == ["made.txt"]
    assert "made.txt" in Path(cap["patch"]).read_text()
    assert sh(wt, "git", "diff", "--cached", "--name-only") == ""
    assert (wt / ".git").read_text() == index
    adopted = engine.adopt_files(sdir, 1, ["made.txt=gpt"], [])
    assert adopted["copied"] == ["made.txt"]
    assert (repo / "made.txt").read_text() == "built\n"
    with pytest.raises(engine.EngineError):
        engine.adopt_files(sdir, 1, ["../evil=gpt"], [])
    engine.remove_worktrees(sdir, None)
    assert not wt.exists()
    assert "weave/gpt" not in sh(repo, "git", "branch", "--list")
    assert engine.load_session(sdir)["worktrees"] == {}


def test_capture_and_adopt_whole_participant(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "a.txt").unlink()
    (wt / "sub" / "new.py").write_text("x = 1\n")
    cap = engine.capture_tree(sdir, 1, "maintainer", None)
    assert cap["deleted"] == ["a.txt"]
    assert cap["changed"] == ["sub/new.py"]
    done = engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    assert done["copied"] == ["sub/new.py"]
    assert not (repo / "a.txt").exists()
    assert (repo / "sub" / "new.py").read_text() == "x = 1\n"


def test_read_only_worktrees_start_from_the_snapshot(repo: Path) -> None:
    (repo / "a.txt").write_text(DIRTY_A)
    sdir = Path(init()["session_dir"])
    made = engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(made["worktrees"]["maintainer"]["path"])
    assert made["worktrees"]["maintainer"]["branch"] is None
    assert (wt / "a.txt").read_text() == DIRTY_A
    engine.remove_worktrees(sdir, None)
    assert not wt.exists()


def test_mutating_init_stashes_and_restore_pops_own_entry(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    (repo / "new.txt").write_text("untracked\n")
    doc = init(command="execute", mutating=True)
    sdir = Path(doc["session_dir"])
    assert doc["stash"]["state"] == "stashed"
    assert sh(repo, "git", "status", "--porcelain") == ""
    (repo / "other.txt").write_text("o")
    sh(repo, "git", "stash", "push", "-q", "--include-untracked", "-m", "unrelated")
    (repo / "synth.txt").write_text("synth\n")
    assert engine.reset_main(sdir)["ok"]
    assert not (repo / "synth.txt").exists()
    assert engine.restore_stash(sdir)["restored"] is True
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert (repo / "new.txt").exists()


def test_reset_main_refuses_without_stash_record_or_missing_stash(repo: Path) -> None:
    sdir = Path(init()["session_dir"])
    with pytest.raises(engine.EngineError, match="no stash record"):
        engine.reset_main(sdir)
    (repo / "a.txt").write_text("user edit\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sh(repo, "git", "stash", "drop")
    with pytest.raises(engine.EngineError, match="missing"):
        engine.reset_main(sdir)


def test_clean_tree_mutating_init_needs_no_stash(repo: Path) -> None:
    doc = init(command="execute", mutating=True)
    assert doc["stash"] == {"state": "none-needed"}
    assert engine.reset_main(Path(doc["session_dir"]))["ok"]
    assert engine.restore_stash(Path(doc["session_dir"]))["restored"] is False


# --- flags, prompts, labels, judges ---------------------------------------


def test_profiles_keep_the_timeout_menu_at_half_and_one_and_a_half() -> None:
    for command, prof in engine.PROFILES.items():
        menu = engine.parse_flags("x", command)["timeout_menu"]
        assert menu["default"] == prof.timeout
        assert menu["quick"] == prof.timeout // 2
        assert menu["long"] == prof.timeout + prof.timeout // 2


def test_cli_flags_and_labels(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO('--mode=deep --cascade why it\'s "odd" $HOME'))
    code = engine.main(["flags", "--command", "ask"])
    doc = json.loads(capsys.readouterr().out)
    assert code == 0
    assert doc["prompt"] == 'why it\'s "odd" $HOME'
    assert doc["flags"] == ["cascade"]
    assert doc["passes"] == 2
    assert doc["timeout"] == 675

    sdir = Path(init()["session_dir"])
    for name in ("maintainer", "skeptic", "builder"):
        (sdir / "pass-0001" / "outputs" / f"{name}.md").write_text(f"from {name}")
    engine.main(["labels", "--session", str(sdir), "--participants", "maintainer,skeptic,builder"])
    labels = json.loads(capsys.readouterr().out)["labels"]
    assert sorted(labels) == ["A", "B", "C"]
    blind = sdir / "pass-0001" / "blind"
    assert (blind / "response-A.md").read_text() == f"from {labels['A']}"
    assert json.loads((sdir / "pass-0001" / "label-map.json").read_text()) == labels


def test_labels_read_variant_outputs_from_the_session_root(repo: Path) -> None:
    sdir = Path(init(command="brainstorm", variants=2)["session_dir"])
    for name in ("maintainer-v1", "maintainer-v2"):
        (sdir / "outputs" / f"{name}.md").write_text(name)
    doc = engine.label_participants(
        sdir, 1, ["maintainer-v1", "maintainer-v2"], outputs=sdir / "outputs"
    )
    blind = sdir / "pass-0001" / "blind"
    assert {(blind / f"response-{k}.md").read_text() for k in doc["labels"]} == {
        "maintainer-v1",
        "maintainer-v2",
    }


def test_bad_flags_exit_nonzero(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("--passes=zero"))
    assert engine.main(["flags", "--command", "ask"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_context_sections_with_full_diff(repo: Path) -> None:
    (repo / "dirty.txt").write_text("x")
    assert "dirty.txt" in engine.context_sections(str(repo))
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "feature")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "main")
    text = engine.context_sections(str(repo), full_diff=True, diff_limit=3)
    assert "## Full diff" in text
    assert "truncated at 3" in text


def test_not_a_repo_reports_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    code = engine.main(["init", "--command", "execute", "--backend", "subagents", "--mutating"])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_init_reads_prompt_and_prompt_composes_variants(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("what\n  does  $X do?"))
    args = ["init", "--command", "ask", "--backend", "subagents", "--prompt-stdin"]
    assert engine.main(args) == 0
    sdir = Path(json.loads(capsys.readouterr().out)["session_dir"])
    assert engine.load_session(sdir)["prompt_summary"] == "what does $X do?"
    body = sdir / "body.md"
    body.write_text("Q")
    out = sdir / "pass-0001" / "prompts" / "builder.md"
    assert engine.main(["prompt", "--lane", "builder", "--file", str(body), "--out", str(out)]) == 0
    text = out.read_text()
    assert text.startswith("You are the Builder.")
    assert "\n\nQ\n\n---\nCRITICAL" in text
    pre = sdir / "pre.md"
    pre.write_text("Be\n  bold.")
    out2 = sdir / "v.md"
    argv = ["prompt", "--lane", "gpt", "--file", str(body), "--out", str(out2), "--variant", "2"]
    assert engine.main([*argv, "--of", "3", "--preamble-file", str(pre)]) == 0
    assert out2.read_text().splitlines()[2] == "Variant 2 of 3: Be bold."


def test_judge_plan_modes(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    stub(bindir, "agent", "exit 0")
    sdir = Path(init(backend="model-clis")["session_dir"])
    rr = [engine.plan_judges(sdir, "round-robin", n)["judges"][0] for n in (1, 2, 3, 4)]
    assert [j["judge"] for j in rr] == ["claude", "agy", "gpt", "claude"]
    assert [j["how"] for j in rr] == ["host", "external", "external", "host"]
    panel = engine.plan_judges(sdir, "panel", 1)
    assert panel["feasibility"] == "full"
    native = Path(init()["session_dir"])
    assert engine.plan_judges(native, "round-robin", 2)["judges"][0]["how"] == "native"
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["agy"], sets=[], link_latest=False,
    )  # fmt: skip
    assert engine.plan_judges(sdir, "panel", 1)["feasibility"] == "degraded"
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["gpt"], sets=[], link_latest=False,
    )  # fmt: skip
    assert engine.plan_judges(sdir, "panel", 1)["mode"] == "host"
    assert engine.plan_judges(sdir, "round-robin", 2)["mode"] == "host"


def judge_text(winner: str, rows: dict[str, dict[str, int]]) -> str:
    cols = list(rows)
    dims = list(next(iter(rows.values())))
    lines = ["| Dimension | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    lines += [f"| {d} | " + " | ".join(str(rows[c][d]) for c in cols) + " |" for d in dims]
    totals = {c: sum(rows[c].values()) for c in cols}
    lines.append("| **Total** | " + " | ".join(str(totals[c]) for c in cols) + " |")
    return (
        "\n".join(lines) + f"\n\n## Winner\n\n**{winner}** with a score of {totals[winner]}/20.\n"
    )


def test_judge_parse_rejects_bad_totals_and_unknown_winner() -> None:
    good = judge_text("a", {"a": {"Q": 9, "C": 8}, "b": {"Q": 5, "C": 5}})
    assert engine.parse_judge(good)["winner_score"] == 17
    bad = good.replace("| 17 | 10 |", "| 18 | 10 |")
    slip = engine.parse_judge(bad)
    assert slip["ok"] is True
    assert slip["totals"]["a"] == 17
    assert slip["winner_score"] == 17
    assert "recomputed as 17" in slip["warnings"][0]
    assert not engine.parse_judge(good.replace("**a** with", "**z** with"))["ok"]
    assert not engine.parse_judge(good.replace("| 9 |", "| 11 |"))["ok"]


def test_judge_parse_flags_a_winner_that_did_not_improve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    new, old = tmp_path / "new.md", tmp_path / "old.md"
    new.write_text(judge_text("a", {"a": {"Q": 7, "C": 7}, "b": {"Q": 1, "C": 1}}))
    old.write_text(judge_text("a", {"a": {"Q": 8, "C": 7}, "b": {"Q": 1, "C": 1}}))
    assert engine.main(["judge-parse", "--file", str(new), "--prior", str(old)]) == 0
    assert json.loads(capsys.readouterr().out)["not_improved"] is True


def test_panel_merge_is_peer_only(tmp_path: Path) -> None:
    files: dict[str, Path] = {}
    for judge, scores in {
        "claude": {"claude-v1": {"Q": 10, "C": 10}, "agy-v1": {"Q": 6, "C": 6}},
        "agy": {"claude-v1": {"Q": 6, "C": 6}, "agy-v1": {"Q": 10, "C": 10}},
    }.items():
        path = tmp_path / f"{judge}.md"
        path.write_text(judge_text("claude-v1", scores))
        files[judge] = path
    broken = tmp_path / "gpt.md"
    broken.write_text("garbage")
    files["gpt"] = broken
    doc = engine.merge_panel(files)
    assert doc["judges_succeeded"] == ["agy", "claude"]
    assert "gpt" in doc["judges_failed"]
    assert doc["peers"]["claude-v1"] == ["agy"]
    assert doc["totals"] == {"claude-v1": 12.0, "agy-v1": 12.0}
    assert doc["tied"] == ["agy-v1", "claude-v1"]
    assert doc["winner"] is None


def test_pass_dir_creates_mutating_subdirs(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    done = engine.make_pass(sdir, 2)
    assert (Path(done["pass_dir"]) / "diffs").is_dir()


def test_bare_session_has_no_workers_or_guard(repo: Path) -> None:
    doc = engine.init_session(
        command="fix-review", backend=None, repo=".", prompt_summary="", passes=1,
        timeout="default", mutating=False, bare=True,
    )  # fmt: skip
    session = engine.load_session(doc["session_dir"])
    assert session["worker_backend"] is None
    assert session["participants"] == []
    assert "guard" not in session
    with pytest.raises(engine.EngineError, match="no guard snapshot"):
        engine.guard_check(Path(doc["session_dir"]))
    with pytest.raises(engine.EngineError, match="needs --backend"):
        engine.init_session(
            command="ask", backend=None, repo=".", prompt_summary="", passes=1,
            timeout="default", mutating=False,
        )  # fmt: skip


def test_mutating_session_finish_skips_the_comparison_and_drops_refs(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sid = engine.load_session(sdir)["session_id"]
    (repo / "adopted.txt").write_text("synthesis\n")
    done = engine.guard_finish(sdir)
    assert done["clean"] is None
    assert done["refs_pruned"] is True
    assert sh(repo, "git", "for-each-ref", f"refs/weave-guard/{sid}/") == ""


def test_context_reports_trunk_branch_and_commits(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "main")
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "change b")
    assert engine.main(["context", "--full-diff"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["trunk"], doc["branch"]) == ("main", "feature")
    assert doc["commits"][0].endswith("change b")
    assert "+b2" in doc["markdown"]


# --- safety: stash, unsafe toplevel, no-repo mode, recovery pins -------------


def test_failed_stash_pop_keeps_the_stash_and_never_advises_dropping_it(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sha = engine.load_session(sdir)["stash"]["sha"]
    (repo / "a.txt").write_text("synthesis\n")
    doc = engine.restore_stash(sdir)
    assert doc["ok"] is False
    assert doc["stash_kept"] is True
    assert doc["stash_sha"] == sha
    assert engine.stash_entry(str(repo), sha) is not None
    assert "drop" not in json.dumps(doc)
    assert doc["overlap"] == ["a.txt"]
    for cmd in doc["recover"]:
        sh(repo, *cmd.split())
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert "synthesis" in sh(repo, "git", "stash", "list")
    assert engine.stash_entry(str(repo), sha) is not None


def test_adopt_then_restore_leaves_synthesis_and_user_changes_before_any_panel(
    repo: Path,
) -> None:
    (repo / "b.txt").write_text("user edit\n")
    (repo / "u.txt").write_text("user untracked\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "sub" / "new.py").write_text("x = 1\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    engine.remove_worktrees(sdir, None)
    assert engine.restore_stash(sdir)["restored"] is True
    assert (repo / "sub" / "new.py").read_text() == "x = 1\n"
    assert (repo / "b.txt").read_text() == "user edit\n"
    assert (repo / "u.txt").exists()
    assert sh(repo, "git", "stash", "list") == ""


@pytest.mark.parametrize("skill", ["execute", "prompt", "architecture"])
def test_write_skills_restore_the_stash_before_presenting_results(skill: str) -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.index("stash-restore") < text.index("present-results.md")


def test_no_skill_or_reference_advises_stash_drop() -> None:
    root = Path(__file__).resolve().parents[1]
    hits = [
        str(p.relative_to(root))
        for folder in ("skills", "references")
        for p in (root / folder).rglob("*.md")
        if "stash drop" in p.read_text(encoding="utf-8")
    ]
    assert hits == []


def fake_home_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, nested: bool) -> Path:
    outer = tmp_path / "homes"
    home = outer / "me" if nested else outer
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    (outer / "f.txt").write_text("x\n")
    sh(outer, "git", "init", "-q", "-b", "main")
    sh(outer, "git", "config", "user.email", "t@example.com")
    sh(outer, "git", "config", "user.name", "t")
    sh(outer, "git", "add", "-A")
    sh(outer, "git", "commit", "-q", "-m", "init")
    return home if not nested else outer


@pytest.mark.parametrize(
    "nested", [False, True], ids=["home-is-toplevel", "toplevel-contains-home"]
)
def test_unsafe_toplevel_is_refused_for_mutating_and_unguarded_when_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: bool
) -> None:
    top = fake_home_repo(tmp_path, monkeypatch, nested=nested)
    monkeypatch.chdir(top)
    (top / "dirty.txt").write_text("keep me\n")
    with pytest.raises(engine.EngineError, match="needs a git repository"):
        init(command="execute", mutating=True)
    assert not (tmp_path / "aip").exists()
    assert sh(top, "git", "stash", "list") == ""
    assert (top / "dirty.txt").read_text() == "keep me\n"
    doc = init(command="brainstorm")
    assert doc["unguarded"] is True
    assert "No repository" in doc["note"]
    assert sh(top, "git", "for-each-ref", "refs/weave-guard/") == ""
    for call in (engine.stash_user_changes, engine.take_guard_snapshot):
        with pytest.raises(engine.EngineError, match="refusing to snapshot"):
            call(str(top), "x")


def test_unsafe_toplevel_rule() -> None:
    assert engine.unsafe_toplevel("/") == "the filesystem root"
    assert engine.unsafe_toplevel("/a/b", {"HOME": "/a/b"}) == "your home directory"
    assert engine.unsafe_toplevel("/a/b/c", {"HOME": "/a/b"}) is None


def test_no_repo_mode_runs_read_only_commands_unguarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bindir: Path
) -> None:
    work = tmp_path / "plain"
    work.mkdir()
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.chdir(work)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    stub(bindir, "codex", "pwd > cwd.txt; ls -A | grep -v cwd.txt > ls.txt; echo ok")
    doc = init(command="refine", backend="model-clis")
    sdir = Path(doc["session_dir"])
    assert doc["repo"] is False
    assert doc["trunk"] is None
    assert engine.guard_check(sdir) == {"ok": True, "violation": False, "unguarded": True}
    assert engine.main(["guard", "check", "--session", str(sdir)]) == 0
    assert engine.guard_resolve(sdir, "revert")["violation"] is False
    assert engine.guard_finish(sdir)["unguarded"] is True
    other = init(command="refine")
    assert other["session_dir"].split("sessions")[0] == doc["session_dir"].split("sessions")[0]
    got = dispatch(sdir, "gpt")
    assert got["ok"] is True
    assert Path(sdir / "scratch").is_dir()
    ctx = engine.context_doc(".", full_diff=True, diff_limit=0)
    assert ctx["repo"] is False
    assert "No repository" in ctx["markdown"]
    made = engine.create_worktrees(sdir, ["maintainer"])["worktrees"]
    assert Path(made["maintainer"]["path"]).is_dir()
    assert not any(Path(made["maintainer"]["path"]).iterdir())
    engine.remove_worktrees(sdir, None)


def test_no_repo_mode_also_covers_a_repository_without_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "fresh"
    work.mkdir()
    sh(work, "git", "init", "-q", "-b", "main")
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.chdir(work)
    assert init(command="ask")["unguarded"] is True


@pytest.mark.parametrize("command", ["execute", "prompt", "architecture", "review"])
def test_commands_that_need_commits_refuse_without_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    work = tmp_path / "plain"
    work.mkdir()
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(work)
    with pytest.raises(engine.EngineError, match="needs a git repository with at least one"):
        init(command=command)
    with pytest.raises(engine.EngineError, match="needs a git repository"):
        engine.init_session(
            command="fix-review", backend=None, repo=".", prompt_summary="", passes=1,
            timeout="default", mutating=False, bare=True,
        )  # fmt: skip


def test_failed_init_leaves_no_session_directory_and_returns_the_stash(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "a.txt").write_text("user edit\n")

    def boom(*_a: object, **_k: object) -> engine.Json:
        msg = "snapshot failed"
        raise engine.EngineError(msg)

    monkeypatch.setattr(engine, "take_guard_snapshot", boom)
    with pytest.raises(engine.EngineError, match="snapshot failed"):
        init(command="execute", mutating=True)
    aip = Path(engine.aip_root())
    assert not list(aip.rglob("session.json"))
    assert not list(aip.rglob("repo.json"))
    assert not any(p.is_dir() for p in aip.rglob("sessions/*/*"))
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert sh(repo, "git", "stash", "list") == ""


def test_guard_finish_keeps_the_pins_reset_main_needs(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sid = engine.load_session(sdir)["session_id"]
    (repo / "synth.txt").write_text("discarded synthesis\n")
    engine.reset_main(sdir)
    assert engine.guard_finish(sdir)["refs_pruned"] is True
    refs = sh(repo, "git", "for-each-ref", "--format=%(refname)", f"refs/weave-guard/{sid}/")
    pins = [r for r in refs.split() if "/pre-reset-" in r]
    assert len(pins) == 1
    assert len(refs.split()) == 1
    assert sh(repo, "git", "show", f"{pins[0]}:synth.txt") == "discarded synthesis\n"


# --- judge parsing, flags, errors, context -----------------------------------


def test_judge_parse_accepts_decimals_and_a_missing_winner_section() -> None:
    text = (
        "| Dimension | claude | agy |\n|---|---|---|\n| Q | 8.5 | 7 |\n| C | 9 | 6.5 |\n"
        "| **Total** | 17.5 | 13.5 |\n"
    )
    doc = engine.parse_judge(text)
    assert doc["ok"], doc["errors"]
    assert doc["totals"] == {"claude": 17.5, "agy": 13.5}
    assert (doc["winner"], doc["winner_declared"], doc["winner_score"]) == ("claude", False, 17.5)
    assert engine.parse_judge(text.replace("17.5", "18.5"))["totals"]["claude"] == 17.5


def test_judge_columns_normalize_role_suffixes_and_blind_labels(tmp_path: Path) -> None:
    named = (
        "| Dimension | claude (Maintainer) | agy - Skeptic |\n|---|---|---|\n| Q | 9 | 5 |\n"
        "| **Total** | 9 | 5 |\n\n## Winner\n\n**claude (Maintainer)** with a score of 9.\n"
    )
    assert engine.parse_judge(named)["columns"] == ["claude", "agy"]
    assert engine.parse_judge(named)["winner"] == "claude"
    blind = (
        "| Dimension | Response A | Response B |\n|---|---|---|\n| Q | 4 | 9 |\n"
        "| **Total** | 4 | 9 |\n\n## Winner\n\nResponse B with a score of 9.\n"
    )
    doc = engine.parse_judge(blind, {"A": "claude-v1", "B": "agy-v1"})
    assert (doc["columns"], doc["winner"]) == (["claude-v1", "agy-v1"], "agy-v1")
    files: dict[str, Path] = {}
    for judge, rows in (("claude", "| Q | 10 | 3 |"), ("agy", "| Q | 2 | 8 |")):
        f = tmp_path / f"{judge}.md"
        cells = [c.strip() for c in rows.split("|")]
        head = f"| Dimension | Response A ({judge}) | Response B |\n|---|---|---|\n{rows}\n"
        f.write_text(head + f"| **Total** | {cells[2]} | {cells[3]} |\n")
        files[judge] = f
    doc2 = engine.merge_panel(files, {"A": "claude-v1", "B": "agy-v1"})
    assert doc2["peers"] == {"agy-v1": ["claude"], "claude-v1": ["agy"]}


def test_flags_are_consumed_only_from_the_leading_block() -> None:
    doc = engine.parse_flags("tool --mode=fast --timeout=30 x", "refine")
    assert doc["prompt"] == "tool --mode=fast --timeout=30 x"
    assert doc["mode"] is None
    assert doc["timeout"] is None
    doc = engine.parse_flags("--mode=fast refine tool --timeout=30", "refine")
    assert (doc["mode"], doc["timeout"], doc["prompt"]) == ("fast", 225, "refine tool --timeout=30")


def test_bad_inputs_report_json_not_tracebacks(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    cases = [
        ["prompt", "--lane", "gpt", "--file", "/nonexistent/x", "--out", str(sdir / "o.md")],
        ["update", "--session", str(sdir), "--set", "x=bad"],
        ["update", "--session", str(sdir), "--set", "novalue"],
        ["update", "--session", str(sdir), "--event", "e", "--event-json", "{"],
        ["capture", "--session", str(sdir), "--participant", "nobody"],
        ["judge-parse", "--file", "/nonexistent/j.md"],
        ["pass-dir", "--session", str(sdir / "missing"), "--pass", "2"],
    ]
    for argv in cases:
        assert engine.main(argv) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False
    body = sdir / "p.md"
    body.write_text("q")
    assert (
        engine.main(
            [
                "dispatch",
                "--session",
                str(sdir),
                "--lane",
                "gpt",
                "--prompt-file",
                str(body),
                "--mutating",
            ]
        )
        == 1
    )
    assert "no worktree registered" in json.loads(capsys.readouterr().out)["error"]


def test_context_falls_back_to_a_local_trunk_without_origin(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "change b")
    assert engine.main(["context"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["base"] == "main"
    assert doc["commits"][0].endswith("change b")
    assert " B " in doc["markdown"] or "B |" in doc["markdown"]


def test_classification_ignores_task_text_echoed_on_stderr(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'for a in "$@"; do echo "$a" >&2; done; echo boom >&2; exit 2')
    sdir, _ = read_only_session()
    sdir_prompt = sdir / "prompt.md"
    sdir_prompt.write_text("Fix the billing rate limit 429 quota exceeded bug")
    got = engine.dispatch_lane(
        sdir, "gpt", n=1, prompt_file=sdir_prompt, timeout=5, mutating=False, rate_wait=0
    )
    assert got["failure_class"] == "crash"
    assert len(got["attempts"]) == 1


def test_plan_judges_with_every_participant_dropped(repo: Path) -> None:
    sdir = Path(init()["session_dir"])
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["maintainer", "skeptic", "builder"], sets=[], link_latest=False,
    )  # fmt: skip
    for mode in ("round-robin", "panel"):
        assert engine.plan_judges(sdir, mode, 1)["mode"] == "host"
