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
    monkeypatch.setattr("sys.stdin", io.StringIO('why --mode=deep it\'s "odd" $HOME --cascade'))
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
    code = engine.main(["init", "--command", "ask", "--backend", "subagents"])
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
    assert "total for a is not the sum" in engine.parse_judge(bad)["errors"][0]
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
